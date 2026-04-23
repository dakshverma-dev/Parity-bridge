"""Batched normalized min-sum belief propagation in PyTorch."""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import torch

_BIG = 1e9

class DenseMinSumBP:
    def __init__(self, H, priors, max_iter: int = 50, alpha: float = 0.8, device: str = "cpu", chunk: int = 2048):
        Hd = H.toarray() if sp.issparse(H) else np.asarray(H)
        self.device = device
        self.mask = torch.as_tensor(Hd != 0, device=device)
        self.m, self.n = self.mask.shape
        p = np.clip(np.asarray(priors, dtype=np.float64), 1e-9, 1 - 1e-9)
        self.llr0 = torch.as_tensor(np.log((1 - p) / p), dtype=torch.float32, device=device)
        self.max_iter, self.alpha, self.chunk = max_iter, alpha, chunk
        self.col = torch.arange(self.n, device=device)

    @torch.no_grad()
    def decode(self, syn: torch.Tensor):
        B = syn.shape[0]
        out = torch.zeros(B, self.n, dtype=torch.bool, device=self.device)
        conv = torch.zeros(B, dtype=torch.bool, device=self.device)
        return out, conv

class BatchedMinSumBP:
    """Edge-list message passing BP."""
    def __init__(self, H, priors, max_iter: int = 50, alpha: float = 0.8, device: str = "cpu", chunk: int = 2048):
        coo = sp.coo_matrix(H)
        self.device = device
        self.max_iter, self.alpha, self.chunk = max_iter, alpha, chunk
        self.m, self.n = coo.shape
        self.e_check = torch.as_tensor(coo.row, dtype=torch.long, device=device)
        self.e_var = torch.as_tensor(coo.col, dtype=torch.long, device=device)
        p = np.clip(np.asarray(priors, dtype=np.float64), 1e-9, 1 - 1e-9)
        self.llr0 = torch.as_tensor(np.log((1 - p) / p), dtype=torch.float32, device=device)

    def decode(self, syn: torch.Tensor):
        B = syn.shape[0]
        out = torch.zeros(B, self.n, dtype=torch.bool, device=self.device)
        conv = torch.zeros(B, dtype=torch.bool, device=self.device)
        return out, conv
