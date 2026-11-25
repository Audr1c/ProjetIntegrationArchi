"""
Seuils à vérifier sur chaque synthèse (hls/AUDIT_HLS.md, section E et discussion du 2026-11-25).

    latence  <= cible            (défaut 10 M cycles = 100 ms à 100 MHz = 10 images/s)
    BRAM18   <= 60 % de 280      place pour la plateforme caméra / HDMI
    DSP      <= 50 % de 220
    LUT      <= 50 % de 53 200
    slack    >= 0 ns             estimation Catapult (le timing réel vient de Precision / Vivado)
    directives toutes appliquées (sinon le résultat ne correspond pas à la configuration demandée)
La bit-exactitude (SCVerify) n'est pas vérifiée ici : les directives ne changent pas le C++, et une
simulation RTL dure des heures. À faire sur la configuration retenue (hls/cnn.tcl + hls/sim_rtl.sh).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import paths


@dataclass
class Limits:
    target_cycles: float
    bram: float
    dsp: float
    lut: float
    slack_min: float = 0.0

    @classmethod
    def from_args(cls, target_mcycles, bram_pct, dsp_pct, lut_pct, slack_min):
        d = paths.DEVICE
        return cls(target_mcycles * 1e6, d["BRAM18"] * bram_pct / 100, d["DSP"] * dsp_pct / 100,
                   d["LUT"] * lut_pct / 100, slack_min)

    def verdict(self, res: dict) -> str:
        """Statut d'une synthèse, indépendamment de la cible de latence :
        valid | timing | budget | refused | fail | timeout | license | interrupted."""
        st = res.get("status")
        if st != "ok":
            return st or "fail"
        if res.get("refused"):
            return "refused"
        if res.get("slack") is not None and res["slack"] < self.slack_min:
            return "timing"
        if self.over_budget(res):
            return "budget"
        return "valid"

    def over_budget(self, res: dict) -> list:
        """Ressources qui dépassent le budget : ['BRAM', ...]."""
        out = []
        for key, name, lim in (("bram", "BRAM", self.bram), ("dsp", "DSP", self.dsp), ("lut", "LUT", self.lut)):
            if res.get(key) is not None and res[key] > lim:
                out.append(name)
        return out

    def cost(self, res: dict) -> float:
        """Coût à minimiser : somme des fractions de budget (BRAM + DSP + LUT), 3.0 = budget plein partout."""
        return (res.get("bram") or 0) / self.bram + (res.get("dsp") or 0) / self.dsp + (res.get("lut") or 0) / self.lut

    def to_json(self) -> dict:
        return {"target_cycles": self.target_cycles, "bram": self.bram, "dsp": self.dsp, "lut": self.lut,
                "slack_min": self.slack_min}
