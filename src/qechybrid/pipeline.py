"""Hybrid surface-code pipeline: fast-path pre-decoder -> global decoder (MWPM) for the rest."""
from __future__ import annotations

import numpy as np
import torch
from .timing import now

class HybridDecoder:
    def __init__(self, matcher, gate=None, mode: str = "nn", device: str = "cpu", chunk: int = 65536, local=None):
        self.matcher, self.gate, self.mode, self.device, self.chunk = matcher, gate, mode, device, chunk
        if mode in ("none", "zero"):
            self.device = "cpu"
        self.local = local

    def _front(self, dets):
        B = len(dets)
        if self.mode == "none":
            return np.zeros(B, bool), np.zeros((B, 1), np.uint8), dets
        if self.mode == "zero":
            return ~dets.any(axis=1), np.zeros((B, 1), np.uint8), dets
        if self.mode == "local":
            resid, flip = self.local.predecode(dets)
            acc = (resid.sum(dim=1) == 0).cpu().numpy()
            return acc, flip.cpu().numpy()[:, None], resid.cpu().numpy()
        z = self.gate.logits(dets)
        acc = (z.abs().amax(-1) >= self.gate.threshold).cpu().numpy()
        return acc, (z > 0).to(torch.uint8).cpu().numpy(), dets

    def decode_batch(self, dets: np.ndarray) -> np.ndarray:
        preds = []
        for i in range(0, len(dets), self.chunk):
            d = dets[i : i + self.chunk]
            acc, p, res = self._front(d)
            out = p.copy()
            rest = ~acc
            if rest.any():
                m = self.matcher.decode_batch(res[rest])
                out[rest] = (p[rest] ^ m) if self.mode == "local" else m
            preds.append(out)
        return np.concatenate(preds) if preds else np.zeros((0, 1), np.uint8)

    def decode_one(self, det: np.ndarray) -> np.ndarray:
        acc, p, res = self._front(det[None])
        if acc[0]:
            return p[0]
        m = self.matcher.decode_one(res[0])
        return (p[0] ^ m) if self.mode == "local" else m
