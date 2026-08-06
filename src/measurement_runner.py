
import asyncio
from dataclasses import replace
import threading
import time

from PySide6.QtCore import QObject, Signal
import pypalmsens as ps

from aurora_method_builder.methods import AuroraStepwiseMethod
from src.measurement_data import (
    AuroraStepCompleted,
    LiveMeasurementStarted,
    LogicalMeasurementRun,
    MeasurementSegment,
    TemperatureSample,
)
from src.temperature_chamber.temperature_controller import TemperatureController, TemperatureProgress


class measurement_runner(QObject):
    progress = Signal(object)

    def __init__(self, instrument, method, temperature_settings=None):
        super().__init__()
        self.instrument = instrument
        self.method = method
        self.temperature_settings = temperature_settings
        self.manager = None
        self.loop = None
        self.abort_requested = False
        self._state_lock = threading.Lock()

    async def measure_with_manager(self, manager):
        try:
            with self._state_lock:
                self.manager = manager
                self.loop = asyncio.get_running_loop()
                abort_requested = self.abort_requested

            if isinstance(self.method, AuroraStepwiseMethod):
                return await self._measure_aurora_stepwise(manager, self.method)

            manager.validate_method(self.method)

            if abort_requested:
                return LogicalMeasurementRun(type(self.method).__name__)

            def on_data(data):
                self.progress.emit(data)

            temperature_controller = self._connect_temperature_controller()
            try:
                self.progress.emit(LiveMeasurementStarted())
                measurement, temperature_samples = await self._measure_palmsens(
                    manager,
                    self.method,
                    on_data,
                    temperature_controller,
                )
            finally:
                if temperature_controller is not None:
                    temperature_controller.close()

            if temperature_controller is None:
                return measurement

            title = getattr(measurement, "title", None) or type(self.method).__name__
            segment = MeasurementSegment(
                index=1,
                label=title,
                source=measurement,
                temperature_samples=temperature_samples,
            )
            return LogicalMeasurementRun(title, [segment])
        finally:
            with self._state_lock:
                self.manager = None
                self.loop = None

    async def _measure_aurora_stepwise(self, manager, stepwise_method: AuroraStepwiseMethod):
        actions = stepwise_method.render_actions()
        if not actions:
            raise RuntimeError("Aurora package did not produce any executable steps.")

        run = LogicalMeasurementRun(stepwise_method.name)
        run_start = time.monotonic()

        if any(action.is_temperature for action in actions) and self.temperature_settings is None:
            raise RuntimeError("This Aurora method contains temperature steps, but the chamber is not enabled.")
        temperature_controller = self._connect_temperature_controller()

        def on_data(data):
            self.progress.emit(data)

        try:
            for action in actions:
                if self._abort_requested():
                    break

                if action.is_temperature:
                    try:
                        await self._execute_temperature_action(temperature_controller, action)
                    except Exception:
                        if not self._abort_requested():
                            raise
                        break
                    continue

                if not action.is_palmsens or action.methodscript is None:
                    continue

                method = ps.MethodScript(script=action.methodscript)
                manager.validate_method(method)
                segment_offset_s = time.monotonic() - run_start
                segment = MeasurementSegment(
                    index=len(run.segments) + 1,
                    label=action.label,
                    source=None,
                    elapsed_offset_s=segment_offset_s,
                    source_step_index=action.source_step_index,
                    step_type=action.step_type,
                    execution_index=action.execution_index,
                )
                self.progress.emit(
                    LiveMeasurementStarted(
                        run_title=run.title,
                        segment=segment,
                    )
                )
                try:
                    measurement, temperature_samples = await self._measure_palmsens(
                        manager,
                        method,
                        on_data,
                        temperature_controller,
                    )
                except Exception:
                    if not self._abort_requested():
                        raise
                    break
                segment = replace(
                    segment,
                    source=measurement,
                    temperature_samples=temperature_samples,
                )
                run.add_segment(segment)
                self.progress.emit(AuroraStepCompleted(segment))

                if self._abort_requested():
                    break
        finally:
            if temperature_controller is not None:
                if self._abort_requested() and self.temperature_settings.stop_on_abort:
                    temperature_controller.stop()
                temperature_controller.close()

        if not run.segments and not self._abort_requested():
            raise RuntimeError("Aurora step-wise execution completed without measurement data.")
        return run

    def _connect_temperature_controller(self) -> TemperatureController | None:
        if self.temperature_settings is None:
            return None

        controller = TemperatureController(self.temperature_settings)
        controller.connect()
        return controller

    async def _measure_palmsens(
        self,
        manager,
        method,
        callback,
        temperature_controller: TemperatureController | None,
    ):
        # Pathway 1: temperature chamber is not enabled
        if temperature_controller is None:
            measurement = await manager.measure(method, callback=callback)
            return measurement, ()

        # Pathway 2: temperature chamber is enabled --> poll temperature and setpoint and store
        samples: list[TemperatureSample] = []
        stop_polling = threading.Event()
        measurement_started_at = time.monotonic()
        polling_task = asyncio.create_task(
            asyncio.to_thread(
                self._poll_temperature,
                temperature_controller,
                stop_polling,
                measurement_started_at,
                samples,
            )
        )

        try:
            measurement = await manager.measure(method, callback=callback)
        finally:
            stop_polling.set()
            await polling_task

        return measurement, tuple(samples)

    @staticmethod
    def _poll_temperature(
        controller: TemperatureController,
        stop_polling: threading.Event,
        measurement_started_at: float,
        samples: list[TemperatureSample],
    ):
        while True:
            poll_started_at = time.monotonic()
            status = controller.poll_status()
            if status is not None:
                samples.append(
                    TemperatureSample(
                        elapsed_s=time.monotonic() - measurement_started_at,
                        temperature_c=status.temperature_c,
                        setpoint_c=status.setpoint_c,
                    )
                )

            poll_duration = time.monotonic() - poll_started_at
            wait_s = max(0.0, controller.settings.poll_interval_s - poll_duration)
            if stop_polling.wait(wait_s):
                return

    # TODO: current architecture hardwires temperature chamber
    # solution: possibly switch to general implementation and non native steps as  modules
    async def _execute_temperature_action(self, temperature_controller, action):
        if temperature_controller is None:
            raise RuntimeError("Temperature chamber is not configured.")

        target_c = action.target_temperature_c
        if target_c is None:
            raise RuntimeError("Temperature step is missing a target temperature.")

        wait_s = action.wait_after_s or 0.0
        self.progress.emit(
            TemperatureProgress(
                target_c=target_c,
                temperature_c=None,
                setpoint_c=None,
                wait_elapsed_s=0.0,
                message=f"Setting chamber to {target_c:.2f} C",
            )
        )

        if action.ramp_rate_c_per_min is not None:
            temperature_controller.set_ramp_rate(action.ramp_rate_c_per_min)
        temperature_controller.start()
        temperature_controller.set_target(target_c)

        status = await asyncio.to_thread(
            temperature_controller.wait_for_temperature_step,
            target_c,
            wait_s,
            self._abort_requested,
            self.progress.emit,
            timer_starts_immediately=action.wait_starts_immediately,
        )
        completion = (
            "Temperature timer completed"
            if action.wait_starts_immediately
            else "Temperature stabilized"
        )
        self.progress.emit(
            TemperatureProgress(
                target_c=target_c,
                temperature_c=status.temperature_c,
                setpoint_c=status.setpoint_c,
                wait_elapsed_s=wait_s,
                message=f"{completion} at {status.temperature_c:.2f} C",
            )
        )

    def abort(self):
        with self._state_lock:
            self.abort_requested = True
            manager = self.manager
            loop = self.loop

        if manager is not None and loop is not None:
            asyncio.run_coroutine_threadsafe(manager.abort(), loop)

    def _abort_requested(self) -> bool:
        with self._state_lock:
            return self.abort_requested
