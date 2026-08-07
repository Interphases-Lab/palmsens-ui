from dataclasses import dataclass
from typing import Any, Callable, get_args

import pypalmsens as ps
from pypalmsens.types import AllowedCurrentRanges


Parser = Callable[[str], Any]
Builder = Callable[[dict[str, Any]], object]


CURRENT_RANGE_OPTIONS: tuple[str, ...] = get_args(AllowedCurrentRanges)
CURRENT_RANGE_FIELD_KEYS = frozenset({"current_range", "applied_current_range"})


@dataclass()
class FieldSpec:
    key: str
    label: str
    default: str
    parser: Parser

    def parse(self, raw_value: str) -> Any:
        value = raw_value.strip()
        if not value:
            raise ValueError(f"{self.label} is required.")

        try:
            return self.parser(value)
        except ValueError as exc:
            raise ValueError(f"Invalid value for {self.label}: {raw_value}") from exc


@dataclass()
class MethodSpec:
    key: str
    label: str
    fields: tuple[FieldSpec, ...]
    builder: Builder

    def default_params(self) -> dict[str, str]:
        return {field.key: field.default for field in self.fields}

    def build_method(self, raw_params: dict[str, str]) -> object:
        parsed_params = {
            field.key: field.parse(raw_params.get(field.key, ""))
            for field in self.fields
        }
        return self.builder(parsed_params)


# Adapts a PyPalmSens technique class to methodspecs parameters.
def _technique_builder(technique_type: type) -> Builder:
    def build(params: dict[str, Any]) -> object:
        return technique_type(**params)

    return build


def _parse_levels(value: str) -> list[dict[str, float]]:
    levels = []
    for raw_level in value.split(","):
        level, duration = raw_level.split(":")
        levels.append({"level": float(level.strip()), "duration": float(duration.strip())})
    return levels


METHOD_SPECS: dict[str, MethodSpec] = {
    "ca": MethodSpec(
        key="ca",
        label="Chrono Amperometry",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("potential", "Potential (V)", "0.0", float),
            FieldSpec("run_time", "Run time (s)", "10.0", float),
        ),
        builder=_technique_builder(ps.ChronoAmperometry),
    ),
    "cv": MethodSpec(
        key="cv",
        label="Cyclic Voltammetry",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("begin_potential", "Begin potential (V)", "-0.5", float),
            FieldSpec("vertex1_potential", "Vertex 1 potential (V)", "0.5", float),
            FieldSpec("vertex2_potential", "Vertex 2 potential (V)", "-0.5", float),
            FieldSpec("step_potential", "Step potential (V)", "0.01", float),
            FieldSpec("scanrate", "Scan rate (V/s)", "0.1", float),
            FieldSpec("n_scans", "Number of scans", "1", int),
        ),
        builder=_technique_builder(ps.CyclicVoltammetry),
    ),
    "acv": MethodSpec(
        key="acv",
        label="AC Voltammetry",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("begin_potential", "Begin potential (V)", "-0.5", float),
            FieldSpec("end_potential", "End potential (V)", "0.5", float),
            FieldSpec("step_potential", "Step potential (V)", "0.1", float),
            FieldSpec("ac_potential", "AC potential RMS (V)", "0.01", float),
            FieldSpec("frequency", "Frequency (Hz)", "100.0", float),
            FieldSpec("scanrate", "Scan rate (V/s)", "1.0", float),
        ),
        builder=_technique_builder(ps.ACVoltammetry),
    ),
    "cc": MethodSpec(
        key="cc",
        label="Chrono Coulometry",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("step1_potential", "Step 1 potential (V)", "0.5", float),
            FieldSpec("step1_run_time", "Step 1 run time (s)", "5.0", float),
            FieldSpec("step2_potential", "Step 2 potential (V)", "0.5", float),
            FieldSpec("step2_run_time", "Step 2 run time (s)", "5.0", float),
        ),
        builder=_technique_builder(ps.ChronoCoulometry),
    ),
    "pot": MethodSpec(
        key="pot",
        label="Chrono Potentiometry",
        fields=(
            FieldSpec("current", "Current multiplier", "0.0", float),
            FieldSpec("applied_current_range", "Applied current range", "100mA", str),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("run_time", "Run time (s)", "1.0", float),
        ),
        builder=_technique_builder(ps.ChronoPotentiometry),
    ),
    "dpv": MethodSpec(
        key="dpv",
        label="Differential Pulse Voltammetry",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("begin_potential", "Begin potential (V)", "-0.5", float),
            FieldSpec("end_potential", "End potential (V)", "0.5", float),
            FieldSpec("step_potential", "Step potential (V)", "0.1", float),
            FieldSpec("pulse_potential", "Pulse potential (V)", "0.05", float),
            FieldSpec("pulse_time", "Pulse time (s)", "0.01", float),
            FieldSpec("scan_rate", "Scan rate (V/s)", "1.0", float),
        ),
        builder=_technique_builder(ps.DifferentialPulseVoltammetry),
    ),
    "eis": MethodSpec(
        key="eis",
        label="Electrochemical Impedance Spectroscopy",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("dc_potential", "DC potential (V)", "0.0", float),
            FieldSpec("ac_potential", "AC potential RMS (V)", "0.01", float),
            FieldSpec("frequency_type", "Frequency type (scan/fixed)", "scan", str),
            FieldSpec("fixed_frequency", "Fixed frequency (Hz)", "1000", float),
            FieldSpec("min_frequency", "Minimum frequency (Hz)", "5.0", float),
            FieldSpec("max_frequency", "Maximum frequency (Hz)", "10000", float),
            FieldSpec("n_frequencies", "Number of frequencies", "11", int),
            FieldSpec("scan_type", "Scan type (fixed/time/potential)", "fixed", str),
            FieldSpec("run_time", "Run time (s)", "10.0", float),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("begin_potential", "Begin potential (V)", "0.0", float),
            FieldSpec("end_potential", "End potential (V)", "0.0", float),
            FieldSpec("step_potential", "Step potential (V)", "0.01", float),
            FieldSpec("min_sampling_time", "Minimum sampling time (s)", "0.5", float),
            FieldSpec("max_equilibration_time", "Maximum equilibration time (s)", "5.0", float),
        ),
        builder=_technique_builder(ps.ElectrochemicalImpedanceSpectroscopy),
    ),
    "fam": MethodSpec(
        key="fam",
        label="Fast Amperometry",
        fields=(
            FieldSpec("current_range", "Current range", "100nA", str),
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("equilibration_potential", "Equilibration potential (V)", "1.0", float),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("potential", "Potential (V)", "0.5", float),
            FieldSpec("run_time", "Run time (s)", "1.0", float),
        ),
        builder=_technique_builder(ps.FastAmperometry),
    ),
    "fcv": MethodSpec(
        key="fcv",
        label="Fast Cyclic Voltammetry",
        fields=(
            FieldSpec("current_range", "Current range", "1uA", str),
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("begin_potential", "Begin potential (V)", "-0.5", float),
            FieldSpec("vertex1_potential", "Vertex 1 potential (V)", "0.5", float),
            FieldSpec("vertex2_potential", "Vertex 2 potential (V)", "-0.5", float),
            FieldSpec("step_potential", "Step potential (V)", "0.1", float),
            FieldSpec("scanrate", "Scan rate (V/s)", "1.0", float),
            FieldSpec("n_scans", "Number of scans", "1", int),
            FieldSpec("n_avg_scans", "Averaged scans", "1", int),
            FieldSpec("n_equil_scans", "Equilibration scans", "1", int),
        ),
        builder=_technique_builder(ps.FastCyclicVoltammetry),
    ),
    "fgis": MethodSpec(
        key="fgis",
        label="Fast Galvanostatic Impedance Spectroscopy",
        fields=(
            FieldSpec("applied_current_range", "Applied current range", "100uA", str),
            FieldSpec("run_time", "Run time (s)", "10.0", float),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("ac_current", "AC current multiplier RMS", "0.01", float),
            FieldSpec("dc_current", "DC current multiplier", "0.0", float),
            FieldSpec("frequency", "Frequency (Hz)", "50000.0", float),
        ),
        builder=_technique_builder(ps.FastGalvanostaticImpedanceSpectroscopy),
    ),
    "fis": MethodSpec(
        key="fis",
        label="Fast Impedance Spectroscopy",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("run_time", "Run time (s)", "10.0", float),
            FieldSpec("dc_potential", "DC potential (V)", "0.0", float),
            FieldSpec("ac_potential", "AC potential RMS (V)", "0.01", float),
            FieldSpec("frequency", "Frequency (Hz)", "50000.0", float),
        ),
        builder=_technique_builder(ps.FastImpedanceSpectroscopy),
    ),
    "gis": MethodSpec(
        key="gis",
        label="Galvanostatic Impedance Spectroscopy",
        fields=(
            FieldSpec("applied_current_range", "Applied current range", "100uA", str),
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("ac_current", "AC current multiplier RMS", "0.01", float),
            FieldSpec("dc_current", "DC current multiplier", "0.0", float),
            FieldSpec("frequency_type", "Frequency type (scan/fixed)", "scan", str),
            FieldSpec("fixed_frequency", "Fixed frequency (Hz)", "1000", float),
            FieldSpec("min_frequency", "Minimum frequency (Hz)", "5.0", float),
            FieldSpec("max_frequency", "Maximum frequency (Hz)", "10000", float),
            FieldSpec("n_frequencies", "Number of frequencies", "11", int),
            FieldSpec("scan_type", "Scan type (fixed/time/current)", "fixed", str),
            FieldSpec("run_time", "Run time (s)", "10.0", float),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("begin_current", "Begin current multiplier", "0.0", float),
            FieldSpec("end_current", "End current multiplier", "0.0", float),
            FieldSpec("step_current", "Current step multiplier", "0.01", float),
            FieldSpec("min_sampling_time", "Minimum sampling time (s)", "0.5", float),
            FieldSpec("max_equilibration_time", "Maximum equilibration time (s)", "5.0", float),
        ),
        builder=_technique_builder(ps.GalvanostaticImpedanceSpectroscopy),
    ),
    "lsp": MethodSpec(
        key="lsp",
        label="Linear Sweep Potentiometry",
        fields=(
            FieldSpec("applied_current_range", "Applied current range", "100uA", str),
            FieldSpec("current_begin", "Begin current multiplier", "-1.0", float),
            FieldSpec("current_end", "End current multiplier", "1.0", float),
            FieldSpec("current_step", "Current step multiplier", "0.01", float),
            FieldSpec("scan_rate", "Scan rate multiplier (/s)", "1.0", float),
        ),
        builder=_technique_builder(ps.LinearSweepPotentiometry),
    ),
    "lsv": MethodSpec(
        key="lsv",
        label="Linear Sweep Voltammetry",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("begin_potential", "Begin potential (V)", "-0.5", float),
            FieldSpec("end_potential", "End potential (V)", "0.5", float),
            FieldSpec("step_potential", "Step potential (V)", "0.1", float),
            FieldSpec("scanrate", "Scan rate (V/s)", "1.0", float),
        ),
        builder=_technique_builder(ps.LinearSweepVoltammetry),
    ),
    "ma": MethodSpec(
        key="ma",
        label="Multi-Step Amperometry",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("n_cycles", "Number of cycles", "1", int),
            FieldSpec("levels", "Levels (potential V:duration s, ...)", "0.0:1.0", _parse_levels),
        ),
        builder=_technique_builder(ps.MultiStepAmperometry),
    ),
    "mp": MethodSpec(
        key="mp",
        label="Multi-Step Potentiometry",
        fields=(
            FieldSpec("applied_current_range", "Applied current range", "1uA", str),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("n_cycles", "Number of cycles", "1", int),
            FieldSpec("levels", "Levels (current multiplier:duration s, ...)", "0.0:1.0", _parse_levels),
        ),
        builder=_technique_builder(ps.MultiStepPotentiometry),
    ),
    "mpad": MethodSpec(
        key="mpad",
        label="Multiple Pulse Amperometry",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("run_time", "Run time (s)", "10.0", float),
            FieldSpec("duration_1", "Pulse 1 duration (s)", "0.1", float),
            FieldSpec("duration_2", "Pulse 2 duration (s)", "0.1", float),
            FieldSpec("duration_3", "Pulse 3 duration (s)", "0.1", float),
            FieldSpec("potential_1", "Pulse 1 potential (V)", "0.0", float),
            FieldSpec("potential_2", "Pulse 2 potential (V)", "0.0", float),
            FieldSpec("potential_3", "Pulse 3 potential (V)", "0.0", float),
        ),
        builder=_technique_builder(ps.MultiplePulseAmperometry),
    ),
    "npv": MethodSpec(
        key="npv",
        label="Normal Pulse Voltammetry",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("begin_potential", "Begin potential (V)", "-0.5", float),
            FieldSpec("end_potential", "End potential (V)", "0.5", float),
            FieldSpec("step_potential", "Step potential (V)", "0.1", float),
            FieldSpec("pulse_time", "Pulse time (s)", "0.01", float),
            FieldSpec("scan_rate", "Scan rate (V/s)", "1.0", float),
        ),
        builder=_technique_builder(ps.NormalPulseVoltammetry),
    ),
    "ocp": MethodSpec(
        key="ocp",
        label="Open Circuit Potentiometry",
        fields=(
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("run_time", "Run time (s)", "1.0", float),
        ),
        builder=_technique_builder(ps.OpenCircuitPotentiometry),
    ),
    "pad": MethodSpec(
        key="pad",
        label="Pulsed Amperometric Detection",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("potential", "Base potential (V)", "0.5", float),
            FieldSpec("pulse_potential", "Pulse potential (V)", "0.05", float),
            FieldSpec("pulse_time", "Pulse time (s)", "0.01", float),
            FieldSpec("mode", "Mode (dc/pulse/differential)", "dc", str),
            FieldSpec("interval_time", "Interval time (s)", "0.1", float),
            FieldSpec("run_time", "Run time (s)", "10.0", float),
        ),
        builder=_technique_builder(ps.PulsedAmperometricDetection),
    ),
    "swv": MethodSpec(
        key="swv",
        label="Square Wave Voltammetry",
        fields=(
            FieldSpec("equilibration_time", "Equilibration time (s)", "0.0", float),
            FieldSpec("begin_potential", "Begin potential (V)", "-0.5", float),
            FieldSpec("end_potential", "End potential (V)", "0.5", float),
            FieldSpec("step_potential", "Step potential (V)", "0.1", float),
            FieldSpec("frequency", "Frequency (Hz)", "10.0", float),
            FieldSpec("amplitude", "Amplitude (V)", "0.05", float),
        ),
        builder=_technique_builder(ps.SquareWaveVoltammetry),
    ),
    "scp": MethodSpec(
        key="scp",
        label="Stripping Chrono Potentiometry",
        fields=(
            FieldSpec("potential_range", "Potential range", "500mV", str),
            FieldSpec("current", "Current multiplier", "0.0", float),
            FieldSpec("applied_current_range", "Applied current range", "100uA", str),
            FieldSpec("end_potential", "End potential (V)", "0.0", float),
            FieldSpec("measurement_time", "Maximum measurement time (s)", "1.0", float),
        ),
        builder=_technique_builder(ps.StrippingChronoPotentiometry),
    ),
}


METHOD_ORDER = tuple(METHOD_SPECS.keys())


def build_method(method_key: str, raw_params: dict[str, str]) -> object:
    return METHOD_SPECS[method_key].build_method(raw_params)
