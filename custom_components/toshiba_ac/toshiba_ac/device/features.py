# Copyright 2022 Kamil Sroka

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import logging
import struct
import typing as t

from toshiba_ac.device.properties import (
    ToshibaAcAirPureIon,
    ToshibaAcFanMode,
    ToshibaAcMeritA,
    ToshibaAcMeritB,
    ToshibaAcMode,
    ToshibaAcPowerSelection,
    ToshibaAcSelfCleaning,
    ToshibaAcStatus,
    ToshibaAcSwingMode,
)
from toshiba_ac.utils import pretty_enum_name

logger = logging.getLogger(__name__)


class ToshibaAcFeatures:
    MERIT_BITS_STRUCT = struct.Struct("????????????????")

    DISABLED_AC_MERIT_B_FOR_MODE: t.Dict[ToshibaAcMode, t.List[ToshibaAcMeritB]] = {
        ToshibaAcMode.AUTO: [
            ToshibaAcMeritB.FIREPLACE_1,
            ToshibaAcMeritB.FIREPLACE_2,
        ],
        ToshibaAcMode.COOL: [
            ToshibaAcMeritB.FIREPLACE_1,
            ToshibaAcMeritB.FIREPLACE_2,
        ],
        ToshibaAcMode.DRY: [
            ToshibaAcMeritB.FIREPLACE_1,
            ToshibaAcMeritB.FIREPLACE_2,
        ],
        ToshibaAcMode.HEAT: [],
        ToshibaAcMode.FAN: [
            ToshibaAcMeritB.FIREPLACE_1,
            ToshibaAcMeritB.FIREPLACE_2,
        ],
    }

    DISABLED_AC_MERIT_A_FOR_MODE: t.Dict[ToshibaAcMode, t.List[ToshibaAcMeritA]] = {
        ToshibaAcMode.AUTO: [
            ToshibaAcMeritA.HEATING_8C,
            ToshibaAcMeritA.SLEEP_CARE,
            ToshibaAcMeritA.FLOOR,
        ],
        ToshibaAcMode.COOL: [
            ToshibaAcMeritA.HEATING_8C,
            ToshibaAcMeritA.SLEEP_CARE,
            ToshibaAcMeritA.FLOOR,
        ],
        ToshibaAcMode.DRY: [
            ToshibaAcMeritA.HIGH_POWER,
            ToshibaAcMeritA.ECO,
            ToshibaAcMeritA.CDU_SILENT_1,
            ToshibaAcMeritA.CDU_SILENT_2,
            ToshibaAcMeritA.HEATING_8C,
            ToshibaAcMeritA.SLEEP_CARE,
            ToshibaAcMeritA.FLOOR,
        ],
        ToshibaAcMode.HEAT: [],
        ToshibaAcMode.FAN: [
            ToshibaAcMeritA.HIGH_POWER,
            ToshibaAcMeritA.ECO,
            ToshibaAcMeritA.CDU_SILENT_1,
            ToshibaAcMeritA.CDU_SILENT_2,
            ToshibaAcMeritA.HEATING_8C,
            ToshibaAcMeritA.SLEEP_CARE,
            ToshibaAcMeritA.FLOOR,
        ],
    }

    def __init__(
        self,
        ac_status: t.List[ToshibaAcStatus],
        ac_mode: t.List[ToshibaAcMode],
        ac_fan_mode: t.List[ToshibaAcFanMode],
        ac_swing_mode: t.List[ToshibaAcSwingMode],
        ac_power_selection: t.List[ToshibaAcPowerSelection],
        ac_merit_b: t.List[ToshibaAcMeritB],
        ac_merit_a: t.List[ToshibaAcMeritA],
        ac_air_pure_ion: t.List[ToshibaAcAirPureIon],
        ac_self_cleaning: t.List[ToshibaAcSelfCleaning],
        ac_energy_report: bool,
    ) -> None:
        self._ac_status = ac_status
        self._ac_mode = ac_mode
        self._ac_fan_mode = ac_fan_mode
        self._ac_swing_mode = ac_swing_mode
        self._ac_power_selection = ac_power_selection
        self._ac_merit_b = ac_merit_b
        self._ac_merit_a = ac_merit_a
        self._ac_air_pure_ion = ac_air_pure_ion
        self._ac_self_cleaning = ac_self_cleaning
        self._ac_energy_report = ac_energy_report

    @classmethod
    def from_merit_string_and_model(cls, merit_feature_hexstring: str, ac_model_id: str) -> ToshibaAcFeatures:
        s_ac_status = list(ToshibaAcStatus)
        s_ac_mode = [ToshibaAcMode.NONE]
        s_ac_fan_mode = list(ToshibaAcFanMode)
        s_ac_swing_mode = [ToshibaAcSwingMode.NONE, ToshibaAcSwingMode.OFF, ToshibaAcSwingMode.SWING_VERTICAL]
        s_ac_power_selection = list(ToshibaAcPowerSelection)
        s_ac_merit_b = [ToshibaAcMeritB.NONE, ToshibaAcMeritB.OFF]
        s_ac_merit_a = [ToshibaAcMeritA.NONE, ToshibaAcMeritA.OFF, ToshibaAcMeritA.SLEEP_CARE, ToshibaAcMeritA.COMFORT]
        s_ac_pure_ion = [ToshibaAcAirPureIon.NONE, ToshibaAcAirPureIon.OFF]
        s_ac_self_cleaning = list(ToshibaAcSelfCleaning)
        s_ac_energy_report = False

        # Make sure merit feature string has 4 characters
        merit_feature_hexstring = f"{merit_feature_hexstring:<04.4}"

        merit_bits = ToshibaAcFeatures.MERIT_BITS_STRUCT.unpack(
            bytes.fromhex("0" + "0".join(f"{int(merit_feature_hexstring, base=16):016b}"))
        )

        s_ac_mode.extend(
            {
                (False, False): [
                    ToshibaAcMode.AUTO,
                    ToshibaAcMode.COOL,
                    ToshibaAcMode.DRY,
                    ToshibaAcMode.FAN,
                    ToshibaAcMode.HEAT,
                ],
                (False, True): [ToshibaAcMode.HEAT],
                (True, False): [
                    ToshibaAcMode.AUTO,
                    ToshibaAcMode.COOL,
                    ToshibaAcMode.DRY,
                    ToshibaAcMode.FAN,
                ],
                (True, True): [
                    ToshibaAcMode.AUTO,
                    ToshibaAcMode.COOL,
                    ToshibaAcMode.DRY,
                    ToshibaAcMode.FAN,
                    ToshibaAcMode.HEAT,
                ],
            }[(merit_bits[6], merit_bits[7])]
        )

        if ac_model_id in ("2", "3"):
            s_ac_merit_a.append(ToshibaAcMeritA.HIGH_POWER)
            s_ac_merit_a.append(ToshibaAcMeritA.ECO)

            if merit_bits[0]:
                s_ac_merit_a.append(ToshibaAcMeritA.FLOOR)

            if merit_bits[1]:
                s_ac_swing_mode.append(ToshibaAcSwingMode.SWING_HORIZONTAL)
                s_ac_swing_mode.append(ToshibaAcSwingMode.SWING_VERTICAL_AND_HORIZONTAL)

            if merit_bits[2]:
                s_ac_merit_a.append(ToshibaAcMeritA.CDU_SILENT_1)
                s_ac_merit_a.append(ToshibaAcMeritA.CDU_SILENT_2)

            if merit_bits[3]:
                s_ac_pure_ion.append(ToshibaAcAirPureIon.ON)

            if merit_bits[4]:
                s_ac_merit_b.append(ToshibaAcMeritB.FIREPLACE_1)
                s_ac_merit_b.append(ToshibaAcMeritB.FIREPLACE_2)

            if merit_bits[5]:
                s_ac_merit_a.append(ToshibaAcMeritA.HEATING_8C)

        if ac_model_id == "3":
            if merit_bits[14]:
                s_ac_swing_mode.append(ToshibaAcSwingMode.FIXED_1)
                s_ac_swing_mode.append(ToshibaAcSwingMode.FIXED_2)
                s_ac_swing_mode.append(ToshibaAcSwingMode.FIXED_3)
                s_ac_swing_mode.append(ToshibaAcSwingMode.FIXED_4)
                s_ac_swing_mode.append(ToshibaAcSwingMode.FIXED_5)

            if merit_bits[15]:
                s_ac_energy_report = True

        return cls(
            s_ac_status,
            s_ac_mode,
            s_ac_fan_mode,
            s_ac_swing_mode,
            s_ac_power_selection,
            s_ac_merit_b,
            s_ac_merit_a,
            s_ac_pure_ion,
            s_ac_self_cleaning,
            s_ac_energy_report,
        )

    def for_ac_mode(self, ac_mode: ToshibaAcMode) -> ToshibaAcFeatures:
        filtered_ac_merit_b = [
            merit_b for merit_b in self.ac_merit_b if merit_b not in self.DISABLED_AC_MERIT_B_FOR_MODE[ac_mode]
        ]
        filtered_ac_merit_a = [
            merit_a for merit_a in self.ac_merit_a if merit_a not in self.DISABLED_AC_MERIT_A_FOR_MODE[ac_mode]
        ]

        return ToshibaAcFeatures(
            self.ac_status,
            self.ac_mode,
            self.ac_fan_mode,
            self.ac_swing_mode,
            self.ac_power_selection,
            filtered_ac_merit_b,
            filtered_ac_merit_a,
            self.ac_air_pure_ion,
            self.ac_self_cleaning,
            self.ac_energy_report,
        )

    @property
    def ac_status(self) -> t.List[ToshibaAcStatus]:
        return self._ac_status

    @property
    def ac_mode(self) -> t.List[ToshibaAcMode]:
        return self._ac_mode

    @property
    def ac_fan_mode(self) -> t.List[ToshibaAcFanMode]:
        return self._ac_fan_mode

    @property
    def ac_swing_mode(self) -> t.List[ToshibaAcSwingMode]:
        return self._ac_swing_mode

    @property
    def ac_power_selection(self) -> t.List[ToshibaAcPowerSelection]:
        return self._ac_power_selection

    @property
    def ac_merit_b(self) -> t.List[ToshibaAcMeritB]:
        return self._ac_merit_b

    @property
    def ac_merit_a(self) -> t.List[ToshibaAcMeritA]:
        return self._ac_merit_a

    @property
    def ac_air_pure_ion(self) -> t.List[ToshibaAcAirPureIon]:
        return self._ac_air_pure_ion

    @property
    def ac_self_cleaning(self) -> t.List[ToshibaAcSelfCleaning]:
        return self._ac_self_cleaning

    @property
    def ac_energy_report(self) -> bool:
        return self._ac_energy_report

    def __str__(self) -> str:
        return ", ".join(
            (
                f"Supported AC statuses: {{{', '.join(pretty_enum_name(e) for e in self.ac_status)}}}",
                f"Supported AC modes: {{{', '.join(pretty_enum_name(e) for e in self.ac_mode)}}}",
                f"Supported AC fan modes: {{{', '.join(pretty_enum_name(e) for e in self.ac_fan_mode)}}}",
                f"Supported AC swing modes: {{{', '.join(pretty_enum_name(e) for e in self.ac_swing_mode)}}}",
                f"Supported AC power selections: {{{', '.join(pretty_enum_name(e) for e in self.ac_power_selection)}}}",
                f"Supported AC merit B: {{{', '.join(pretty_enum_name(e) for e in self.ac_merit_b)}}}",
                f"Supported AC merit A: {{{', '.join(pretty_enum_name(e) for e in self.ac_merit_a)}}}",
                f"Supported AC air pure ion: {{{', '.join(pretty_enum_name(e) for e in self.ac_air_pure_ion)}}}",
                f"Supported AC self cleaning: {{{', '.join(pretty_enum_name(e) for e in self.ac_self_cleaning)}}}",
                f"Supported AC energy report: {'Yes' if self.ac_energy_report else 'No'}",
            )
        )
