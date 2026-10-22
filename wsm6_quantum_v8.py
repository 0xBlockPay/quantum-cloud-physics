#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSM6-Q v8 — PARCEL MODEL + A&G-INSPIRED PROGNOSTIC ACTIVATION + TWOMEY
             + PARTICLE-WEIGHTED LOG-NORMAL CCN SPECTRUM
==========================================================================

Direction carried over from v7 (design decision after the v6 review): no further
Grover variants or VQE are developed. Everything except the spectrum-mean estimator is
CLASSICAL convective physics — exactly as in real WRF/ICON/IFS schemes, where a
quantum accelerator (if it existed) would plug into precisely the same spot:
the expensive averaging over the CCN spectrum.

Honest naming (v6 reviewer's decision):
  * the activation scheme is an "A&G-INSPIRED PROGNOSTIC ACTIVATION SCHEME"
    (differential supersaturation formulation motivated by Abdul-Razzak &
    Ghan 1995) — NOT the full A&G scheme: we do not solve the asymptotic formula
    S_max(N_a, w); instead a prognostic dS/dt with vapor competition is used;
    * the quantum component = an estimator of the mean <f_i> over the aerosol spectrum
        (IAA m=0, shot-based measurement: P(a=1)); QAE decoding is used ONLY for
        diagnostics/verification and does not speed up the model.

New in v8 (the reviewer's main physics fix — the only scientific change):
    * <f_i> = sum(f_i)/N (v7: mean over RADIUS BINS) is replaced by the
        PARTICLE-POPULATION WEIGHTED MEAN:  <f_i> = sum(w_i f_i) / sum(w_i),
        where w_i ~ exp(-(ln(r_i/r_mode))^2 / (2 ln^2 sigma_g)) — the log-normal
        CCN spectrum. In the atmosphere the extreme bins (20 nm, 500 nm) hold far
        fewer particles than the vicinity of r_mode; the weights N_i are those counts.
    * QUANTUM PART: the initial state is no longer the uniform superposition
        (1/sqrt(N)) sum_i |i> but  sum_i sqrt(w_i) |i> — the amplitudes represent the
        real aerosol spectrum. Then P(a=1) returns DIRECTLY the physically correct
        mean:  P(a=1) = sum_i w_i f_i;
    * the IAA diffuser (m>=1, QAE diagnostics) now reflects the WEIGHTED state:
        S_phi = V R0 V^dagger, where V = prep o H_idx and R0 is the reflection about
        the uniform superposition — the Grover/QAE formulas remain satisfied (T2);
    * [T10] selftest: weight conservation + peak at r_mode + monotonicity of
        S_max(w, N_ccn) for constant w;
    * [T11] selftest: |psi_i|^2 == w_i — direct verification that build_prep_ops()
        really prepares the state sum sqrt(w_i)|i>
        (amplitude encoding of the CCN spectrum), not just the weights alone;
    * [T4] extended: CRY decomposition (multiple controls) == native version on the
        full state vector (protection of the CUDA-Q backend);
    * the VQE block (H2O-aerosol) MOVED to a separate vqe_demo.py — it is not part
        of the model; SELFTEST v6 -> v8 fix and the previously missing test [T10] added.

New in v7:
    * --smax : reference S_max(w, N_ccn) curve from CLASSICAL integration of A&G
                          at constant w (separating activation physics from thermal forcing)
                          + comparison with the model's prognostic S_peak;
    * --twomey: full Twomey experiment (50..3000 cm^-3) split into two channels:
                          condensation (droplet surface area, Twomey) vs autoconversion
                          (rain suppression, Albrecht); CSV + plots;
    * w_at_Speak diagnostic — w compared against the S_max curve.

Architektura v8:

    Thermodynamics (CLASSICAL)
  |
    |-- environment profile theta_env(z), qv_env(z)  -> CAPE / CIN / LFC
    |-- parcel model: dT/dt (pseudo-adiabat), z(t), w(t)
  |-- buoyancy B = g*(theta_v,p - theta_v,env)/theta_v,env
    |-- dw/dt = B - eps*w   (effective drag, tau_drag)
    |     -> FEEDBACK LOOP: latent heating changes T -> B -> w -> S
  |
    CCN activation (CLASSICAL + quantum mean estimator)
  |
    |-- log-normal aerosol spectrum, N = 2^N_IDX dry-radius bins
  |-- kappa-Koehler: S_crit(i), r_crit(i)   [Petters & Pruppacher]
    |-- A&G-inspired prognostic activation (motivated by Abdul-Razzak & Ghan 1995):
    |     dS/dt = adiabatic supply(z, w) - vapor competition(S, Nd, r_bar)
    |   irreversible activation: a bin activates once S > S_crit(i)
    |-- f(S,T) = <f_i> — THE ACTIVATED-FRACTION MEAN — THE ONLY QUANTUM SPOT
    |     (v8: PARTICLE-WEIGHTED <f_i> = sum w_i f_i; state sum sqrt(w_i)|i>;
    |      IAA m=0 in the loop; QAE m=0..3 as report/verification)
    |-- Nd = N_ccn * f  -> cloud droplet number concentration (prognostic variable)
  |
    Cloud microphysics (CLASSICAL, dependence on Nd -> Twomey effect)
  |
    |-- condensation (Fuchs-Stevens, bulk: dqc/dt ~ S*Nd*r_bar)
    |     -> TWOMEY CHANNEL: larger Nd = larger total droplet surface area
    |        (Nd*r_bar ~ Nd^(2/3)) = faster condensation = more qc
    |-- autoconversion: threshold Q_CRIT(Nd) = water needed for r_bar > r_coll
    |     + collision efficiency E(r_bar) -> larger Nd = less rain
    |     (ALBRECHT CHANNEL: precipitation suppression)
    |-- accretion (qr collects qc), sedimentation/rainout of qr

Running:
    pip install cudaq
    python wsm6_quantum_v8.py --selftest                 # T1..T11
        python wsm6_quantum_v8.py --backend mock             # full run (CPU)
        python wsm6_quantum_v8.py --backend cudaq            # IAA on CUDA-Q
        python wsm6_quantum_v8.py --twomey                   # full Twomey experiment + CSV/PNG
        python wsm6_quantum_v8.py --smax                     # S_max(w, N_ccn) reference vs prognostic S_peak
    python wsm6_quantum_v8.py --nccn 3000 --duration 2400
        python wsm6_quantum_v8.py --r-mode 80 --sigma-g 1.7  # log-normal CCN spectrum

Honest limitations (methodological):
    * a single, one-dimensional parcel — no horizontal transport, turbulence or
        advection; drag is an effective parameter (tau_drag), not an LES model;
    * activation: scheme INSPIRED BY A&G (1995) in differential form (S as the
        state) rather than the asymptotic formula S_max(N_a, w) — more direct, but it
        requires a small enough dt (here dt_sub = 0.5 s); the reference curve
        S_max(w, N_ccn) is computed separately (--smax) for comparison;
    * autoconversion is a parameterization (threshold + E(r_bar)), not a spectral
        collision model;
    * the quantum part estimates the WEIGHTED MEAN <f_i> = sum w_i f_i (log-normal
        particle weights; initial state sum sqrt(w_i)|i>; measurement P(a=1), IAA m=0);
        this is a spectrum-mean estimator, NOT a speedup of regression/microphysics;
        QAE decoding is diagnostic only. The advantage over classical summation applies
        in an oracle model where each f_i is expensive (full version: an arithmetic
        oracle computing S_crit(i) from |i>).
"""


from __future__ import annotations
import argparse
import math
import sys

try:
    import cudaq
    from cudaq import spin
    HAVE_CUDAQ = True
except Exception:
    cudaq = None
    spin = None
    HAVE_CUDAQ = False

import numpy as np

# ============================== PARAMETRY ==================================
N_IDX        = 6                 # index qubits -> N = 2^N_IDX (default 64)
MS           = (1, 2, 3)         # IAA iterations for selftest / decoding
SHOTS        = 4096

# --- physical constants ---
R_GAS = 8.314462618              # J/(mol K)
K_B   = 1.380649e-23             # J/K
N_A   = 6.02214076e23            # 1/mol
M_L   = 0.018015                 # kg/mol (H2O)
RHO_L = 998.0                    # kg/m^3

# --- aerosol / Koehler (sea salt by default) ---
RHO_S  = 2200.0                  # kg/m^3 solute density (NaCl ~2200)
M_S    = 0.05844                 # kg/mol masa molowa NaCl
VAN_T_HOFF = 2.0                # van't Hoff factor nu (NaCl -> Na+ + Cl- : nu~2)
KAPPA  = 1.0                     # hygroscopicity multiplier on the osmotic term (1.0=full salt)
R_MIN  = 20e-9                   # m, minimum dry radius of the spectrum
R_MAX  = 500e-9                  # m, maximum dry radius of the spectrum
DELTA_ACT = 5e-4                 # width of the logistic smoothing of activation

# --- log-normal CCN spectrum: particle weights (v8) ---
R_MODE   = 80e-9                  # m, modal radius of the log-normal distribution
SIGMA_G  = 1.7                    # geometric standard deviation (sigma_g)

# qubit layout (NATIVE version):
#   q[0]           = ancilla (we measure P(a=1))
#   q[1..N_IDX]    = index bits, LSB=q[1]
#   q[N_IDX+1]     = work
def n_qubits_native(): return N_IDX + 2

IDX_Q  = lambda: list(range(1, 1 + N_IDX))
def work_q(): return N_IDX + 1
ANC    = 0

# kernel parameter names: hex — ALWAYS valid Python/CUDA-Q identifiers
# (the old th0..thz scheme broke for N_IDX>=6, i.e. 64+ bins)
TH_NAMES = ["th" + format(k, "x") for k in range(2 ** N_IDX)]

BACKEND = None          # globalny backend (ustawiany w main/make_backend)


# ============================== FIZYKA KOHLERA =============================
def surface_tension(T: float) -> float:
    """sigma(T) [N/m] — linear approximation for water."""
    return (75.83 - 0.147 * (T - 273.15)) * 1e-3


def kohlert_coefficients(r_dry: float, T: float, kappa: float = KAPPA):
    """(K [m], C [m^3]) for a dry particle of radius r_dry.

    Rownanie Köhlera:  ln S(r) = K/r − C/r³
      K = 2σM_w/(ρ_w R T)                    [m]   (Kelvin effect — curvature)
      C = κ · (3 ν n_s M_w)/(4 π ρ_w)        [m³]  (solute term: van't Hoff + Raoult)

    Dimensional derivation (a reviewer will start here, so step by step):
      n_s = (ρ_s/M_s)·(4/3)π r_dry³          [mol]  moles of solute in the dry particle
        ρ_s/M_s : [kg/m³]/[kg/mol] = [mol/m³];  × r_dry³ [m³]  ->  [mol]      ✓
      C/κ = (3 ν n_s M_w)/(4 π ρ_w):
        n_s·M_w : [mol]·[kg/mol] = [kg]                 (solute mass)
        /ρ_w    : [kg]/[kg/m³]  = [m³]                                       ✓
      wiec C [m³], a C/r³ [-];  ln S bezwymiarowy.                          ✓

    Note: kappa is here a MULTIPLIER on the full osmotic term (scale of effective
    hygroscopicity; 1.0 = full sea salt with nu=2). The previous version wrongly
    multiplied kappa AND rho_s/M_s, double-counting the solute — fixed here.
    """
    sigma = surface_tension(T)
    K = 2.0 * sigma * M_L / (RHO_L * R_GAS * T)                              # [m]
    n_s = (RHO_S / M_S) * (4.0 / 3.0) * math.pi * r_dry ** 3                 # [mol]
    C = kappa * (3.0 * VAN_T_HOFF * n_s * M_L) / (4.0 * math.pi * RHO_L)     # [m³]
    return K, C


def kohlert_critical_supersat(r_dry: float, T: float, kappa: float = KAPPA):
    """S_crit [RH ratio] — Abdul-Razzak & Ghan activation from the Koehler curve maximum.

    ln S(r) = K/r − C/r³  reaches its maximum at r* = sqrt(3C/K);
    S_crit = exp(K/r* − C/r*³).
    """
    K, C = kohlert_coefficients(r_dry, T, kappa)
    if C <= 0.0:
        return float("inf")
    r_star = math.sqrt(3.0 * C / K)
    return math.exp(K / r_star - C / r_star ** 3)


def aerosol_spectrum(n: int):
    """N dry radii, geometric (log-normal) spacing in [R_MIN, R_MAX]."""
    if n == 1:
        return [math.sqrt(R_MIN * R_MAX)]
    return [R_MIN * (R_MAX / R_MIN) ** (k / (n - 1)) for k in range(n)]


def aerosol_weights(n: int, r_mode: float = R_MODE, sigma_g: float = SIGMA_G):
    """Particle weights w_i for n spectrum bins (normalized: sum(w) = 1).

    Log-normal CCN distribution: density of PARTICLE NUMBER per unit ln(r):
        dN/dln r ~ exp(-(ln r - ln r_mode)^2 / (2 ln^2 sigma_g))
    The aerosol_spectrum() bins are geometric (equal step in ln r), so the number
    of particles N_i in a bin is proportional to the density at the bin center:
        N_i ~ exp(-(ln(r_i/r_mode))^2 / (2 ln^2 sigma_g)),  w_i = N_i / sum_j N_j.

    The PARTICLE-POPULATION mean is then <f> = sum w_i f_i — not the mean over
    radii, sum f_i / N (v7), which gave the 20 nm and 500 nm bins equal weight.
    udzial, chociaz w atmosferze skrajne biny zawieraja kilkakrotnie mniej
    czastek niz okolice r_mode.
    """
    w = []
    for rd in aerosol_spectrum(n):
        x = math.log(rd / r_mode)
        w.append(math.exp(-(x * x) / (2.0 * math.log(sigma_g) ** 2)))
    s = sum(w)
    return [wi / s for wi in w]


def activation_probabilities(S_amb: float, T: float, kappa: float = KAPPA):
    """f_i = liquid activated fraction per aerosol bin at S_amb.

    f_i = 1/(1+exp(-(S_amb − Sc_i)/δ)) — smoothing of the jump (Sc<S -> active).
    Each f_i requires solving Koehler (expensive in the full quantum version).
    """
    n = 2 ** N_IDX
    rds = aerosol_spectrum(n)
    out = []
    for rd in rds:
        Sc = kohlert_critical_supersat(rd, T, kappa)
        x = (S_amb - Sc) / DELTA_ACT
        x = max(-50.0, min(50.0, x))          # clip anti-overflow
        out.append(1.0 / (1.0 + math.exp(-x)))
    return out


def encode_from_probs(probs: list[float]) -> list[float]:
    """theta_i such that sin^2(theta_i/2) = f_i ∈ [0,1]."""
    return [2.0 * math.asin(math.sqrt(min(1.0, max(0.0, p)))) for p in probs]


# ===================== IAA CIRCUIT BUILDERS (ONE for both backends) =======
# op = ("h",q)|("x",q)|("z",q)|("ry",q,coeff,i)|("cx",c,t)
#      |("mcx",controls,target)|("mcz",qs)   <- natywne; decompose_ops() -> cx/ccx/cz
def _oracle_ops(sign: int, i: int) -> list:
    ops = []
    idx = IDX_Q(); w = work_q()
    bits = [(i >> j) & 1 for j in range(N_IDX)]
    for j in range(N_IDX):
        if bits[j] == 0:
            ops.append(("x", idx[j]))
    ops.append(("mcx", list(idx), w))          # work = AND(bits after X)
    ops.append(("cx", w, ANC))                 # C-Ry(sign·θ_i) gadget
    ops.append(("ry", ANC, -sign * 0.5, i))
    ops.append(("cx", w, ANC))
    ops.append(("ry", ANC, +sign * 0.5, i))
    ops.append(("mcx", list(idx), w))          # uncompute work
    for j in range(N_IDX):
        if bits[j] == 0:
            ops.append(("x", idx[j]))
    return ops


def _reflect_psi0_ops() -> list:
    """S_ψ0 = H_idx · X_all · MCZ(all) · X_all · H_idx (correct reflection)."""
    nq = n_qubits_native(); ops = []
    for j in IDX_Q():
        ops.append(("h", j))
    for q in range(nq):
        ops.append(("x", q))
    ops.append(("mcz", list(range(nq))))
    for q in range(nq):
        ops.append(("x", q))
    for j in IDX_Q():
        ops.append(("h", j))
    return ops


def build_prep_ops(weights: list[float]) -> list:
    """State preparation: |0...0> -> sum_i sqrt(w_i) |i> (idx register).

    Recursive amplitude encoding (MSB->LSB): at each level a rotation of the
    qubit by the angle from probability p1 = sum(w, branch 1)/sum(w, node);
    prefix bits equal to 0 are toggled with X before/after the CRY (negative control).
    Ancilla and work stay in |0>. Cost: N-1 rotations + O(N) X gates.

    This is the KEY v8 fix: the amplitudes represent the real aerosol spectrum,
    so P(a=1) after the oracle returns sum_i w_i f_i (the particle mean),
    not (1/N) sum_i f_i (the radius-bin mean).
    """
    n = len(weights); ops = []

    def rec(lo, hi, depth):
        if hi - lo <= 1:
            return
        mid = (lo + hi) // 2
        tot = sum(weights[lo:hi])
        if tot <= 0.0:
            return
        p1 = sum(weights[mid:hi]) / tot
        bit = N_IDX - 1 - depth
        q = bit + 1
        ang = 2.0 * math.asin(math.sqrt(min(1.0, max(0.0, p1))))
        controls, flips = [], []
        for b in range(bit + 1, N_IDX):            # prefiks (bity wyzsze)
            ctrl = b + 1
            if (lo >> b) & 1:
                controls.append(ctrl)
            else:
                ops.append(("x", ctrl)); controls.append(ctrl); flips.append(ctrl)
        if not controls:
            ops.append(("ryv", q, ang))
        else:
            ops.append(("cry", controls, q, ang))
        for c in flips:
            ops.append(("x", c))
        rec(lo, mid, depth + 1); rec(mid, hi, depth + 1)

    rec(0, n, 0)
    return ops


def unprep_ops(weights: list[float]) -> list:
    """Adjoint of build_prep_ops (reversed order; angle signs flipped)."""
    out = []
    for op in reversed(build_prep_ops(weights)):
        if op[0] == "ryv":
            out.append(("ryv", op[1], -op[2]))
        elif op[0] == "cry":
            out.append(("cry", list(op[1]), op[2], -op[3]))
        elif op[0] == "x":
            out.append(("x", op[1]))
        else:
            raise ValueError("unprep: unknown operation %s" % op[0])
    return out


def build_iaa_ops(m: int, weights: list[float] = None) -> list:
    """Full IAA circuit (v8: WEIGHTED initial state).

    weights=None : |ψ0> = (1/sqrt(N)) sum_i |i>   (uniform, v7 behavior);
    weights      : |φ>  = sum_i sqrt(w_i) |i>     (real CCN spectrum).

    For m=0: P(a=1) = sum w_i f_i directly (for weights=None: uniform mean).
    Iteracje (m>=1): Q = O_f · S_φ · O_f† · S_G, gdzie
        S_φ = V R0 V^dagger,  V = prep o H_idx   (R0 = reflection about |ψ0>).
    Since V|ψ0> = |φ>, the operator S_φ is the full reflection I - 2|φ><φ| and
    the Grover/QAE formulas remain satisfied for the weighted state (selftest T2).
    """
    ops = []
    if weights is None:
        for j in IDX_Q():
            ops.append(("h", j))
    else:
        ops += build_prep_ops(weights)
    order = list(range(2 ** N_IDX))
    for i in order:
        ops += _oracle_ops(+1, i)
    for _ in range(m):
        ops.append(("z", ANC))
        for i in reversed(order):
            ops += _oracle_ops(-1, i)
        if weights is None:
            ops += _reflect_psi0_ops()
        else:
            # S_phi = V R0 V^dagger ; applied to a state: first V^dagger,
            # then R0, then V (i.e. in the circuit: unprep, H_idx, R0, H_idx, prep)
            ops += unprep_ops(weights)
            for j in IDX_Q():
                ops.append(("h", j))
            ops += _reflect_psi0_ops()
            for j in IDX_Q():
                ops.append(("h", j))
            ops += build_prep_ops(weights)
        for i in order:
            ops += _oracle_ops(+1, i)
    return ops


# ===================== DECOMPOSITION MCX/MCZ -> cx/ccx/cz (Barenco ladder) =
def decompose_ops(ops: list):
    """Splits mcx/mcz into a Toffoli ladder with a SHARED pool of clean ancillas.

    Returns (new_ops, n_qubits_decomp). The pool starts at n_qubits_native().
    Requirement: pool ancillas are in |0> before the operation (true in the full circuit,
    since every decomposition uncomputes its ancillas back to |0>).
    """
    nq = n_qubits_native()
    # pool size = the max(n-2) needed by a single gate
    need = 0
    for op in ops:
        if op[0] == "mcx":
            need = max(need, len(op[1]) - 2)
        elif op[0] == "mcz":
            need = max(need, len(op[1]) - 2)
        elif op[0] == "cry" and len(op[1]) >= 2:
            need = max(need, len(op[1]) - 1)
    pool0 = nq
    new_ops = []
    for op in ops:
        if op[0] == "mcx":
            controls, target = op[1], op[2]; n = len(controls)
            if n == 1:
                new_ops.append(("cx", controls[0], target))
            elif n == 2:
                new_ops.append(("ccx", controls[0], controls[1], target))
            else:
                anc = [pool0 + k for k in range(n - 2)]
                new_ops.append(("ccx", controls[0], controls[1], anc[0]))
                for i in range(2, n - 1):
                    new_ops.append(("ccx", anc[i - 2], controls[i], anc[i - 1]))
                new_ops.append(("ccx", anc[n - 3], controls[n - 1], target))
                for i in range(n - 2, 1, -1):
                    new_ops.append(("ccx", anc[i - 2], controls[i], anc[i - 1]))
                new_ops.append(("ccx", controls[0], controls[1], anc[0]))
        elif op[0] == "mcz":
            qs = op[1]; n = len(qs)
            if n == 1:
                new_ops.append(("z", qs[0]))
            elif n == 2:
                new_ops.append(("cz", qs[0], qs[1]))
            else:
                anc = [pool0 + k for k in range(n - 2)]
                new_ops.append(("ccx", qs[0], qs[1], anc[0]))
                for i in range(2, n - 1):
                    new_ops.append(("ccx", anc[i - 2], qs[i], anc[i - 1]))
                new_ops.append(("cz", anc[n - 3], qs[n - 1]))
                for i in range(n - 2, 1, -1):
                    new_ops.append(("ccx", anc[i - 2], qs[i], anc[i - 1]))
                new_ops.append(("ccx", qs[0], qs[1], anc[0]))
        elif op[0] == "cry":
            controls, target, ang = op[1], op[2], op[3]; n = len(controls)
            if n == 1:
                new_ops.append(("cry", [controls[0]], target, ang))
            elif n == 2:
                a = pool0
                new_ops.append(("ccx", controls[0], controls[1], a))
                new_ops.append(("cry", [a], target, ang))
                new_ops.append(("ccx", controls[0], controls[1], a))
            else:
                # Toffoli ladder: anc[n-2] = AND(all controls), then a single cry
                anc = [pool0 + k for k in range(n - 1)]
                new_ops.append(("ccx", controls[0], controls[1], anc[0]))
                for i in range(2, n - 1):
                    new_ops.append(("ccx", anc[i - 2], controls[i], anc[i - 1]))
                new_ops.append(("ccx", anc[n - 3], controls[n - 1], anc[n - 2]))
                new_ops.append(("cry", [anc[n - 2]], target, ang))
                new_ops.append(("ccx", anc[n - 3], controls[n - 1], anc[n - 2]))
                for i in range(n - 2, 1, -1):
                    new_ops.append(("ccx", anc[i - 2], controls[i], anc[i - 1]))
                new_ops.append(("ccx", controls[0], controls[1], anc[0]))
        else:
            new_ops.append(op)
    return new_ops, nq + need


# ===================== STATE-VECTOR SIMULATOR (mock / reference) ===========
def _gate_single(psi, q, M):
    """Single-qubit gate; convention: bit q = (st>>q)&1 (LSB=q[0])."""
    dim = len(psi); out = np.zeros_like(psi)
    for st in range(dim):
        b = (st >> q) & 1; base = st & ~(1 << q)
        out[base] += M[0, b] * psi[st]
        out[base | (1 << q)] += M[1, b] * psi[st]
    return out


def _gate_cx(psi, c, t):
    """CNOT; convention: bit = (st>>q)&1."""
    dim = len(psi); out = np.zeros_like(psi)
    for st in range(dim):
        bit = ((st >> c) & 1) << t
        out[st ^ bit] = psi[st]
    return out


def _gate_ccx(psi, a, b, t):
    dim = len(psi); out = np.zeros_like(psi)
    for st in range(dim):
        if ((st >> a) & 1) and ((st >> b) & 1):
            out[st ^ (1 << t)] = psi[st]
        else:
            out[st] = psi[st]
    return out


def _gate_cz(psi, a, b):
    dim = len(psi); out = psi.copy()
    for st in range(dim):
        if ((st >> a) & 1) and ((st >> b) & 1):
            out[st] = -psi[st]
    return out


def _gate_mcx(psi, controls, target):
    dim = len(psi); out = np.zeros_like(psi)
    for st in range(dim):
        if all(((st >> q) & 1) for q in controls):
            out[st ^ (1 << target)] = psi[st]
        else:
            out[st] = psi[st]
    return out


def _gate_mcz(psi, qs):
    dim = len(psi); out = psi.copy()
    for st in range(dim):
        if all(((st >> q) & 1) for q in qs):
            out[st] = -psi[st]
    return out


def _gate_cry(psi, controls, target, angle):
    """Controlled R_y (any number of controls); convention: bit = (st>>q)&1."""
    M = _mat("ry", angle)
    dim = len(psi); out = np.zeros_like(psi)
    for st in range(dim):
        if all(((st >> q) & 1) for q in controls):
            b = (st >> target) & 1; base = st & ~(1 << target)
            out[base] += M[0, b] * psi[st]
            out[base | (1 << target)] += M[1, b] * psi[st]
        else:
            out[st] = psi[st]
    return out


def _mat(kind, angle=0.0):
    c, s = math.cos(angle / 2), math.sin(angle / 2)
    if kind == "ry":
        return np.array([[c, -s], [s, c]], complex)
    if kind == "h":
        return np.array([[1, 1], [1, -1]], complex) / math.sqrt(2)
    if kind == "x":
        return np.array([[0, 1], [1, 0]], complex)
    if kind == "z":
        return np.diag([1.0, -1.0]).astype(complex)


def simulate(ops: list, angles: list, n_q: int):
    """Simulates the full circuit; returns the state vector (n_q qubits)."""
    dim = 2 ** n_q
    psi = np.zeros(dim, complex); psi[0] = 1.0
    for op in ops:
        k = op[0]
        if k in ("ry", "h", "x", "z"):
            q = op[1]
            M = _mat(k, op[2] * angles[op[3]] if k == "ry" else 0.0)
            psi = _gate_single(psi, q, M)
        elif k == "ryv":
            psi = _gate_single(psi, op[1], _mat("ry", op[2]))
        elif k == "cry":
            psi = _gate_cry(psi, op[1], op[2], op[3])
        elif k == "cx":
            psi = _gate_cx(psi, op[1], op[2])
        elif k == "ccx":
            psi = _gate_ccx(psi, op[1], op[2], op[3])
        elif k == "cz":
            psi = _gate_cz(psi, op[1], op[2])
        elif k == "mcx":
            psi = _gate_mcx(psi, op[1], op[2])
        elif k == "mcz":
            psi = _gate_mcz(psi, op[1])
    return psi


def ancilla_prob(ops: list, angles: list) -> float:
    """P(q0=1) after the full NATIVE circuit (exact)."""
    psi = simulate(ops, angles, n_qubits_native())
    p = 0.0
    for st in range(len(psi)):
        if (st >> 0) & 1:
            p += abs(psi[st]) ** 2
    return float(p)


def work_clean(ops: list, angles: list) -> bool:
    psi = simulate(ops, angles, n_qubits_native())
    p0 = 0.0
    for st in range(len(psi)):
        if (st >> work_q()) & 1:
            continue
        p0 += abs(psi[st]) ** 2
    return p0 > 1 - 1e-9



# ===================== DECODING (global) ==================================
def decode_fbar(p_by_m: dict, m_list=MS) -> float:
    """β* = argmin_β Σ_m |sin²((2m+1)β) − p_m|;  f = sin²(β)."""
    best_f, best_err = 0.0, float("inf")
    for k in range(4000):
        beta = math.pi * (k + 0.5) / 8000.0
        err = sum((math.sin((2 * m + 1) * beta) ** 2 - p_by_m[m]) ** 2 for m in m_list)
        if err < best_err:
            best_err, best_f = err, math.sin(beta) ** 2
    return best_f


# ===================== BACKENDY ===========================================
class MockBackend:
    """State-vector simulator of full circuits (numerical reference)."""
    name = "mock"

    def __init__(self, shots=SHOTS):
        self.shots = shots
        self.rng = np.random.default_rng(42)

    def _measure(self, ops, angles):
        p_exact = ancilla_prob(ops, angles)
        k = self.rng.binomial(self.shots, min(1.0, max(0.0, p_exact)))
        return k / self.shots

    def estimate_mean(self, angles: list[float], weights=None) -> float:
        """Weighted mean <f_i> = sum w_i f_i via the m=0 circuit (exact in the model)."""
        return self._measure(build_iaa_ops(0, weights), angles)

    def iaa_estimate(self, angles: list[float], weights=None) -> tuple[float, dict]:
        """Returns (f_hat, {m: p_m}). For a non-uniform oracle, f_hat = p_0."""
        p_by_m = {0: self._measure(build_iaa_ops(0, weights), angles)}
        for m in MS:
            p_by_m[m] = self._measure(build_iaa_ops(m, weights), angles)
        return p_by_m[0], p_by_m


if HAVE_CUDAQ:
    _KERNEL_CACHE = {}

    def build_cudaq_kernel(m: int, weights):
        """Builds the IAA kernel with the CUDA-Q *builder* API (no source strings).

        Native multi-control gates are used directly: cx/cz/cry accept a LIST of
        control qubits, so mcx/mcz/cry need no Toffoli decomposition. The theta_i
        values are runtime float arguments; the CCN-spectrum prep angles (ryv/cry)
        are baked constants.
        """
        n_params = 2 ** N_IDX
        kernel, *args = cudaq.make_kernel(*([float] * n_params))
        q = kernel.qalloc(n_qubits_native())          # anc(0) + idx(1..N_IDX) + work(N_IDX+1)
        for op in build_iaa_ops(m, weights):
            k = op[0]
            if k == "h":
                kernel.h(q[op[1]])
            elif k == "x":
                kernel.x(q[op[1]])
            elif k == "z":
                kernel.z(q[op[1]])
            elif k == "ry":                            # ("ry", qubit, coeff, i): RY(coeff*theta_i)
                kernel.ry(op[2] * args[op[3]], q[op[1]])
            elif k == "ryv":                           # baked constant rotation angle
                kernel.ry(op[2], q[op[1]])
            elif k == "cry":                           # ("cry", controls, target, ang)
                kernel.cry(op[3], [q[c] for c in op[1]], q[op[2]])
            elif k == "cx":                            # single control -> CNOT
                kernel.cx(q[op[1]], q[op[2]])
            elif k == "mcx":                           # ("mcx", controls, target)
                kernel.cx([q[c] for c in op[1]], q[op[2]])
            elif k == "mcz":                           # ("mcz", qs); CZ symmetric -> last = target
                kernel.cz([q[c] for c in op[1][:-1]], q[op[1][-1]])
            else:
                raise ValueError("build_cudaq_kernel: unknown op %s" % k)
        return kernel

    def _compile_kernels():
        """Builds the IAA kernels for the CURRENT N_IDX/weights (lazy, per backend)."""
        key = (N_IDX, R_MODE, SIGMA_G)
        if key in _KERNEL_CACHE:
            return _KERNEL_CACHE[key]
        weights = aerosol_weights(2 ** N_IDX, R_MODE, SIGMA_G)
        ns = {("iaa_kernel_m%d" % m): build_cudaq_kernel(m, weights) for m in list(MS) + [0]}
        _KERNEL_CACHE[key] = ns
        return ns

    class CudaqBackend:
        name = "cudaq"

        def __init__(self, shots=SHOTS):
            self.shots = shots
            self._ns = _compile_kernels()

        def _p1(self, kernel, angles):
            res = cudaq.sample(kernel, *angles, shots_count=self.shots)
            counts = res.counts                         # dict[str, int] (attribute, not a call)
            return sum(c for bs, c in counts.items() if bs[0] == "1") / self.shots

        def estimate_mean(self, angles: list[float], weights=None) -> float:
            # weights are baked into the kernel at build time; arg kept for mock-parity
            return self._p1(self._ns["iaa_kernel_m0"], angles)

        def iaa_estimate(self, angles: list[float], weights=None) -> tuple[float, dict]:
            p_by_m = {m: self._p1(self._ns["iaa_kernel_m%d" % m], angles) for m in [0] + list(MS)}
            return p_by_m[0], p_by_m

    def make_backend(kind="auto", shots=SHOTS):
        global BACKEND
        if kind == "cudaq" and not HAVE_CUDAQ:
            sys.exit("CUDA-Q nie zainstalowane (pip install cudaq). Uzyj --backend mock.")
        if kind in ("cudaq", "auto") and HAVE_CUDAQ:
            print("[info] backend: cudaq (builder API, native multi-control gates)")
            BACKEND = CudaqBackend(shots)
            return BACKEND
        print("[info] backend: mock (state-vector simulator, native version)")
        BACKEND = MockBackend(shots)
        return BACKEND

else:
    def make_backend(kind="auto", shots=SHOTS):
        global BACKEND
        if kind == "cudaq":
            sys.exit("CUDA-Q nie zainstalowane (pip install cudaq). Uzyj --backend mock.")
        print("[info] backend: mock (state-vector simulator, native version)")
        BACKEND = MockBackend(shots)
        return BACKEND


# ===================== VQE — PRZENIESIONE DO vqe_demo.py ==================
# v8 reviewer's decision: the VQE block (H2O-aerosol, cudaq.observe) is NOT part
# of the model and has no prognostic connection to it — for cleanliness of
# publikacji wylaczono go do osobnego skryptu `vqe_demo.py` (ten sam kod).

# ==================== THERMODYNAMICS / ENVIRONMENT PROFILE ==================
R_D   = 287.04                # J/(kg K) gas constant of dry air
C_P   = 1005.0                # J/(kg K)
L_V   = 2.501e6               # J/kg latent heat of vaporization
G_ACC = 9.81                  # m/s^2
KAPPA_D = R_D / C_P           # ~0.2856 (theta exponent)
P0    = 101325.0              # Pa
H_P   = 8600.0                # m, pressure scale height (~R_D*T/g)
R_V   = 461.5                 # J/(kg K) gas constant of water vapor
D_V   = 2.6e-5                # m^2/s diffusivity of vapor in air

def pressure(z: float) -> float:
    return P0 * math.exp(-z / H_P)


def esat(T: float) -> float:
    """Saturation vapor pressure [Pa] (Buck/AL88, adequate for 240-310 K)."""
    return 611.2 * math.exp(17.67 * (T - 273.15) / (T - 29.65))


def q_sat(T: float, p: float = P0) -> float:
    """Vapor mixing ratio [kg/kg] at saturation."""
    e = esat(T)
    return 0.622 * e / (p - e)


def rho_air(T: float, p: float) -> float:
    return p / (R_D * T)


def vpt(T: float, qv: float, p: float) -> float:
    """Virtual potential temperature theta_v [K].

    theta_v = T_v*(P0/p)^kappa_d ;  T_v = T*(1+0.61*qv) (cloud water neglected).
    Note: theta increases with height for a given T — hence the factor is (P0/p)^kappa,
    NOT (p/P0)^kappa (T = theta*(p/P0)^kappa).
    """
    return T * (1.0 + 0.61 * qv) * (P0 / p) ** KAPPA_D


def buoyancy(theta_vp: float, theta_ve: float) -> float:
    """B = g*(theta_v,p - theta_v,env)/theta_v,env  [m/s^2]."""
    return G_ACC * (theta_vp - theta_ve) / theta_ve


class EnvProfile:
    """Environment profile: surface superadiabatic layer (SA) +
    mixed BL + capping inversion (cap) + free troposphere (FT).

    Typical configuration for a cumulus of moderate energy:
    strong surface heating produces a thin superadiabatic layer that acts as the
    TRIGGER of convection (a parcel from below has higher theta than the environment);
    above the BL lies a cap (inversion) limiting the cloud height.

      SA  [0, z_sa):          theta decreasing from theta_bl+dth_sa to theta_bl
      BL  [z_sa, z_cap0):     theta = theta_bl, constant qv (mixed layer)
      CAP[z_cap0, z_cap1):    increasing theta (inversion), dry qv
      FT  [z_cap1, ...):      strongly increasing theta (stable), dry qv
    """

    def __init__(self, theta_bl=293.0, dth_sa=2.5, z_sa=400.0,
                 qv_bl=0.007, dq_bl=-1.5e-6, z_cap0=2000.0, dth_cap=5.0e-3,
                 z_cap1=3000.0, dth_ft=10.0e-3, qv_dry=0.002):
        self.theta_bl, self.dth_sa, self.z_sa = theta_bl, dth_sa, z_sa
        self.qv_bl, self.dq_bl = qv_bl, dq_bl
        self.z_cap0, self.dth_cap, self.z_cap1 = z_cap0, dth_cap, z_cap1
        self.dth_ft, self.qv_dry = dth_ft, qv_dry

    def theta(self, z: float) -> float:
        if z < self.z_sa:
            return self.theta_bl + self.dth_sa * (1.0 - z / self.z_sa)
        if z < self.z_cap0:
            return self.theta_bl
        if z < self.z_cap1:
            return self.theta_bl + self.dth_cap * (z - self.z_cap0)
        return self.theta_bl + self.dth_cap * (self.z_cap1 - self.z_cap0) \
               + self.dth_ft * (z - self.z_cap1)

    def qv(self, z: float) -> float:
        if z < self.z_cap0:
            # slightly decreasing qv in the BL (subsidence at the top of the mixed layer)
            return max(0.0, self.qv_bl + self.dq_bl * z)
        return self.qv_dry

    def T(self, z: float) -> float:
        # T = theta*(p/P0)^kappa_d  (theta = T*(P0/p)^kappa_d)
        return self.theta(z) * (pressure(z) / P0) ** KAPPA_D

    def theta_v(self, z: float) -> float:
        p = pressure(z)
        return vpt(self.T(z), self.qv(z), p)


def cape_cin(env: EnvProfile, z0=100.0, top=5000.0, dz=25.0):
    """CAPE/CIN/LFC for a parcel lifted from z0 (pseudo-adiabat).

    Zwraca (cape [J/kg], cin [J/kg], lfc [m]). Standardowa definicja:
    CIN = -int B dz (gdzie B<0, od z0 do LFC), CAPE = int B dz (gdzie B>0).
    """
    T = env.T(z0); qv = env.qv(z0); W = qv
    cape = cin = 0.0; lfc = None
    z = z0
    while z < top:
        p_new = pressure(z + dz)
        T_dry = T * (p_new / pressure(z)) ** KAPPA_D   # cooling during ascent
        qs = q_sat(T_dry, p_new)
        if W > qs:                       # saturated: condensation + latent heating
            dq = W - qs
            T = T_dry + L_V / C_P * dq
            qv = qs
        else:                            # unsaturated: dry adiabatic
            T = T_dry; qv = W
        B = buoyancy(vpt(T, qv, p_new), env.theta_v(z + dz))
        if lfc is None and W > qs:      # LFC = parcel saturation level
            lfc = z + dz
        if B < 0.0:
            cin -= B * dz
        else:
            cape += B * dz
        z += dz
    return cape, cin, lfc


# ================== QUANTUM ESTIMATOR OF THE SPECTRUM MEAN ================
class QuantumActivationEstimator:
    """THE ONLY quantum spot in v8 (design decision):

        aerosol spectrum -> S_crit(i) [kappa-Koehler] -> f_i(S,T)
        -> |phi> = sum_i sqrt(w_i) |i>   (weights of the log-normal CCN spectrum)
        -> IAA m=0, measurement P(a=1)  =>  f_hat = <f_i>_weights = sum w_i f_i

    v8: the mean is WEIGHTED OVER PARTICLES (not over radius bins, as in v7) —
    the quantum-state amplitudes represent the real aerosol spectrum.
    In the model's time loop m=0 is used; QAE decoding (m=0..MS) via
    .qae_report() — diagnostic only. Cache: re-evaluation only when |dS| > 1e-4
    or |dT| > 0.5 K, since f(S,T) is smooth and the quantum measurement is the costliest part.
    """

    def __init__(self, backend, kappa: float = KAPPA):
        self.backend = backend
        self.kappa = kappa
        self.n_calls = 0
        self._S = None; self._T = None; self._f = None
        self.history = []          # (S, T, f_exact, f_hat)
        self.weights = aerosol_weights(2 ** N_IDX, R_MODE, SIGMA_G)  # particle weights

    def mean_activated_fraction(self, S: float, T: float) -> float:
        if self._S is not None and abs(S - self._S) < 1e-4 and abs(T - self._T) < 0.5:
            return self._f
        probs = activation_probabilities(S, T, self.kappa)
        angles = encode_from_probs(probs)
        f_hat = self.backend.estimate_mean(angles, self.weights)   # <-- QUANTUM (m=0)
        f_exact = sum(w * p for w, p in zip(self.weights, probs))  # particle mean
        self.n_calls += 1
        self._S, self._T, self._f = S, T, f_hat
        self.history.append((S, T, f_exact, f_hat))
        return f_hat

    def qae_report(self, S: float, T: float) -> dict:
        """Full QAE decoding (m=0..MS) — for the report/verification."""
        probs = activation_probabilities(S, T, self.kappa)
        angles = encode_from_probs(probs)
        f_hat0, p_by_m = self.backend.iaa_estimate(angles, self.weights)
        self.n_calls += len(MS) + 1
        return {"f_exact": sum(w * p for w, p in zip(self.weights, probs)),
                "f_mean_radius": sum(probs) / len(probs),   # (diagnostic: v7 radius-bin mean)
                "p_by_m": p_by_m,
                "f_qae": decode_fbar(p_by_m)}


# ===================== PARCEL MODEL + A&G + MICROPHYSICS ===================
R_ACT_MIN = 3.0e-6          # m, minimum radius of a freshly activated droplet
R_BAR_MAX = 500e-6          # m, upper limit of r_bar (numerical stability as Nd->0)
R_COLL    = 45.0e-6         # m, "collisional" radius (autoconversion threshold)
Q_CRIT_MIN = 0.3e-3         # kg/kg, lower bound of the autoconversion threshold
TAU_AUTO  = 120.0           # s, timescale of autoconversion
C_ACC     = 3.0e-4          # accretion qr<-qc (carried over from v5)
W_RAIN_MAX = 9.0            # m/s, maximum rain fall speed


def droplet_radius(qc: float, nd: float) -> float:
    """Mean droplet radius r_bar = (3 qc/(4 pi rho_w Nd))^(1/3),
    clamped to [R_ACT_MIN, R_BAR_MAX] (stability as Nd->0)."""
    if nd <= 0.0 or qc <= 0.0:
        return R_ACT_MIN
    r = (3.0 * qc / (4.0 * math.pi * RHO_L * nd)) ** (1.0 / 3.0)
    return min(R_BAR_MAX, max(R_ACT_MIN, r))


def autoconversion_flux(qc: float, nd: float) -> float:
    """qc->qr flux [kg/kg/s] depending on Nd (first Twomey forcing).

    Threshold Q_CRIT(Nd): the amount of water at which r_bar reaches R_COLL —
    more droplets = more water needed for the same mean radius.
    E(r_bar) = 1/(1+(R_COLL/r_bar)^4) — collision efficiency increasing with size.
    """
    if nd <= 0.0 or qc <= Q_CRIT_MIN:
        return 0.0
    r_bar = droplet_radius(qc, nd)
    v_coll = (4.0 / 3.0) * math.pi * R_COLL ** 3
    q_crit = max(Q_CRIT_MIN, RHO_L * v_coll * nd / rho_air(280.0, P0))
    if qc <= q_crit:
        return 0.0
    E = 1.0 / (1.0 + (R_COLL / r_bar) ** 4)
    return (qc - q_crit) / TAU_AUTO * E


# ===================== S_max(w, N_ccn) REFERENCE — CLASSICAL A&G ==========
def classical_activated_fraction(S_ratio: float, T: float, kappa: float = KAPPA):
    """f(S,T) = <f_i> classically — the same physics as the quantum estimator.

    v8: WEIGHTED OVER PARTICLES (log-normal CCN spectrum), consistent with
    the IAA circuit, which prepares the state sum sqrt(w_i)|i>.
    """
    probs = activation_probabilities(S_ratio, T, kappa)
    weights = aerosol_weights(2 ** N_IDX, R_MODE, SIGMA_G)
    return sum(w * p for w, p in zip(weights, probs))


def smax_reference(env: EnvProfile, n_ccn_m3: float, w_const: float,
                   kappa: float = KAPPA, z0=100.0, duration=1200.0,
                   dt_sub=0.5, z_stop=None):
    """Reference curve S_max(w, N_ccn): A&G-INSPIRED integration at
    CONSTANT w (no buoyancy/drag) — the pure activation response to forcing.

    The S physics is identical to the prognostic model: adiabatic cooling,
    Fuchs-Stevens vapor competition (rate ~ S*Nd*r_bar), irreversible
    activation f(S,T). Returns S_max and the conditions at its occurrence.
    """
    z, T = z0, env.T(z0)
    qv, qc, Nd, S = env.qv(z0), 0.0, 0.0, 0.0
    saturated = False
    t = 0.0
    if z_stop is None:
        z_stop = env.z_cap0 + 500.0
    res = {"S_max": 0.0, "t_smax": float("nan"), "z_smax": float("nan"),
           "Nd_at_smax": float("nan")}
    while t < duration and z < z_stop:
        p_old = pressure(z)
        z_new = z + w_const * dt_sub
        p_new = pressure(z_new)
        T_dry = T * (p_new / p_old) ** KAPPA_D
        qs = q_sat(T_dry, p_new)
        if not saturated:
            T, z = T_dry, z_new
            if qv >= qs:                          # LCL at constant w
                saturated = True
                S_inst = qv / qs - 1.0
                Nd = n_ccn_m3 * classical_activated_fraction(1.0 + S_inst, T_dry, kappa)
                if Nd > 0.0:
                    dm = Nd * (4.0 / 3.0) * math.pi * R_ACT_MIN ** 3 \
                         * RHO_L / rho_air(T_dry, p_new)
                    qc += dm; qv -= dm
            t += dt_sub
            continue
        S_inst = max(0.0, qv / qs - 1.0)
        if Nd > 0.0 and qc > 0.0:
            r_bar = droplet_radius(qc, Nd)
            rate_c = 4.0 * math.pi * D_V * S_inst * Nd * r_bar / qs
        else:
            rate_c = 0.0
        dS_cons = min(rate_c * dt_sub, S_inst)
        dq_cond = dS_cons * qs
        T_new = T_dry + L_V / C_P * dq_cond
        qv -= dq_cond; qc += dq_cond
        S_now = max(0.0, qv / q_sat(T_new, p_new) - 1.0)
        Nd_new = n_ccn_m3 * classical_activated_fraction(1.0 + S_now, T_new, kappa)
        dNd = max(0.0, Nd_new - Nd)
        if dNd > 0.0:
            dm = dNd * (4.0 / 3.0) * math.pi * R_ACT_MIN ** 3 \
                 * RHO_L / rho_air(T_new, p_new)
            qc += dm; qv -= dm
        Nd = Nd_new
        qs_new = q_sat(T_new, p_new)
        S = max(0.0, qv / qs_new - 1.0)
        if S > res["S_max"]:
            res["S_max"] = S
            res["t_smax"], res["z_smax"], res["Nd_at_smax"] = t, z_new, Nd
        T, z = T_new, z_new
        t += dt_sub
    return res


def smax_grid(env: EnvProfile, n_ccn_list=(50, 100, 300, 1000, 3000),
              w_list=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0), kappa=KAPPA,
              duration=1200.0):
    """Grid of S_max(w, N_ccn) [percent] — classical."""
    grid = {}
    for nccn in n_ccn_list:
        row = []
        for w in w_list:
            r = smax_reference(env, nccn * 1e4, w, kappa, duration=duration)
            row.append(r["S_max"] * 100.0)
        grid[nccn] = row
    return {"w_list": list(w_list), "n_ccn_list": list(n_ccn_list),
            "grid": grid}


def smax_interp_row(row, ws, w):
    """Linear interpolation of S_max(w) [percent] along one row of the grid."""
    if w <= ws[0]: return row[0]
    if w >= ws[-1]: return row[-1]
    for i in range(len(ws) - 1):
        if ws[i] <= w <= ws[i + 1]:
            a = (w - ws[i]) / (ws[i + 1] - ws[i])
            return row[i] * (1.0 - a) + row[i + 1] * a
    return row[-1]


class ParcelCloudModel:
    """Parcel with w(t) coming from thermals (version B/C):

      dw/dt = B(z, T, qv) - eps*w ;   dz/dt = w
      dS/dt  = adiabatic supply (qs drops during cooling)
               - vapor competition (droplet growth, Fuchs-Stevens)
      Nd     = N_ccn * f(S,T),  f = <f_i> — the quantum estimator

    Mass balance: W = qv + qc + qr conserved (rainout accounted separately).
    """

    def __init__(self, env: EnvProfile, n_ccn_m3: float, estimator,
                 z0=100.0, w0=0.5, drag_tau=40.0, dt_sub=0.5):
        self.env = env
        self.N_a = n_ccn_m3                 # m^-3 (the whole CCN spectrum)
        self.est = estimator
        self.z, self.w = z0, w0
        self.T = env.T(z0)
        self.qv = env.qv(z0)
        self.qc = 0.0; self.qr = 0.0
        self.Nd = 0.0                       # m^-3 aktywowane kropelki
        self.S = 0.0                        # supersaturation (ratio - 1)
        self.rain_out = 0.0
        self.eps = 1.0 / drag_tau
        self.dt_sub = dt_sub
        self.saturated = False
        self.z_lfc = None
        self.t = 0.0
        self.W0 = self.qv + self.qc + self.qr
        # run diagnostics
        self.max_w = 0.0; self.max_S = 0.0; self.top_z = z0
        self.max_qc = 0.0; self.Nd_peak = 0.0
        self.w_at_Speak = w0                 # w at the time of S_peak (to compare with S_max(w))
        self.qc_from_cond = 0.0              # kg/kg: condensation + nucleation (Twomey channel)
        self.qc_from_auto = 0.0              # kg/kg: autoconversion + accretion (Albrecht channel)

    # ------------------ elementary step (dt_sub) --------------------------
    def _substep(self, h: float):
        env = self.env
        p_old = pressure(self.z)

        # --- 1) buoyancy and vertical momentum ----------------------------
        B = buoyancy(vpt(self.T, self.qv, p_old), env.theta_v(self.z))
        w_new = self.w + (B - self.eps * self.w) * h
        z_new = max(0.0, self.z + 0.5 * (self.w + w_new) * h)
        p_new = pressure(z_new)
        # diagnostics (in both branches: saturated and unsaturated)
        self.max_w = max(self.max_w, w_new)
        self.top_z = max(self.top_z, z_new)

        # --- 2) adiabatic cooling during ascent ---------------------------
        T_dry = self.T * (p_new / p_old) ** KAPPA_D    # cooling during ascent
        qs = q_sat(T_dry, p_new)

        if not self.saturated:
            # unsaturated: qv conserved, S=0; LFC when qv >= qs
            self.T, self.z, self.w = T_dry, z_new, w_new
            if self.qv >= qs:
                self.saturated = True
                self.z_lfc = z_new
                # seed: first activation at the S available in this step
                S_inst = self.qv / qs - 1.0
                f = self.est.mean_activated_fraction(1.0 + S_inst, T_dry)
                self.Nd = self.N_a * f
                if self.Nd > 0.0:
                    dm = self.Nd * (4.0 / 3.0) * math.pi * R_ACT_MIN ** 3 \
                         * RHO_L / rho_air(T_dry, p_new)
                    self.qc += dm
                    self.qv -= dm
                    self.qc_from_cond += dm
            return

        # --- 3) saturated: supply vs competition (A&G in differential form) -
        S_inst = max(0.0, self.qv / qs - 1.0)
        # adiabatic supply: during cooling qs drops, so S grows on its own
        # from the fact that qv is conserved (T_dry < T). We do not add it directly —
        # it follows from the balance below.
        if self.Nd > 0.0 and self.qc > 0.0:
            r_bar = droplet_radius(self.qc, self.Nd)
            # Vapor competition (Fuchs-Stevens): flux to a SPHERICAL droplet
            #   m_dot = 4 pi r D_v dc  (gradient ~1/r, so flux ~ r, NOT r^2!)
            # dS/dt = -Nd*4 pi r_bar D_v c_s S / (rho_air q_s),  c_s = rho_air q_s
            #   -> rate_c = 4 pi D_v S Nd r_bar / q_s   (rho_air cancels out)
            rate_c = 4.0 * math.pi * D_V * S_inst * self.Nd * r_bar / qs
        else:
            rate_c = 0.0
        dS_cons = min(rate_c * h, S_inst)

        # condensation consumed by existing droplets -> latent heating
        dq_cond = dS_cons * qs
        T_new = T_dry + L_V / C_P * dq_cond
        self.qv -= dq_cond
        self.qc += dq_cond
        self.qc_from_cond += dq_cond

        # --- 4) activation of new bins (irreversible) ---------------------
        S_now = max(0.0, self.qv / q_sat(T_new, p_new) - 1.0)
        f = self.est.mean_activated_fraction(1.0 + S_now, T_new)
        Nd_new = self.N_a * f
        dNd = max(0.0, Nd_new - self.Nd)
        if dNd > 0.0:
            dm = dNd * (4.0 / 3.0) * math.pi * R_ACT_MIN ** 3 \
                 * RHO_L / rho_air(T_new, p_new)
            self.qc += dm
            self.qv -= dm
            self.qc_from_cond += dm
        self.Nd = Nd_new

        # --- 5) end-of-step state ------------------------------------------
        qs_new = q_sat(T_new, p_new)
        self.S = max(0.0, self.qv / qs_new - 1.0)
        self.T, self.z, self.w = T_new, z_new, w_new

        # --- 6) microphysics (dependence on Nd -> Twomey) ------------------
        flux = autoconversion_flux(self.qc, self.Nd)
        dq = min(flux * h, self.qc)
        self.qc -= dq; self.qr += dq
        self.qc_from_auto += dq
        if self.qc > 0.0 and self.qr > 0.0:          # accretion
            r_bar = droplet_radius(self.qc, self.Nd)
            dq2 = min(C_ACC * self.qc * self.qr * (r_bar / 20e-6) * h, self.qc)
            self.qc -= dq2; self.qr += dq2
            self.qc_from_auto += dq2
        if self.qr > 0.0:                             # rainout (sedimentation)
            w_r = min(W_RAIN_MAX, 0.1 * math.sqrt(self.qr * 1e3))
            frac = min(1.0, w_r * h / max(z_new - 500.0, 1.0))
            self.rain_out += self.qr * frac
            self.qr *= (1.0 - frac)

        if self.S > self.max_S:
            self.max_S = self.S
            self.w_at_Speak = self.w          # w at the moment S_peak is reached
        self.max_qc = max(self.max_qc, self.qc)
        self.Nd_peak = max(self.Nd_peak, self.Nd)

    # ------------------ macroscopic step ----------------------------------
    def step(self, dt: float):
        n_sub = max(1, int(round(dt / self.dt_sub)))
        h = dt / n_sub
        for _ in range(n_sub):
            self._substep(h)
            self.t += h

    def state(self):
        return {"t_s": round(self.t, 1), "z_m": round(self.z, 1),
                "w_ms": round(self.w, 3), "T_K": round(self.T, 2),
                "S_pct": round(self.S * 100, 4),
                "qv_gkg": round(self.qv * 1e3, 4), "qc_gkg": round(self.qc * 1e3, 4),
                "qr_gkg": round(self.qr * 1e3, 4),
                "Nd_cm3": round(self.Nd / 1e4, 2),
                "opad_gkg": round(self.rain_out * 1e3, 4)}

    def mass_error_pct(self) -> float:
        W = self.qv + self.qc + self.qr + self.rain_out
        return abs(W - self.W0) / max(self.W0, 1e-12) * 100.0


# ===================== TWOMEY SWEEP (1st aerosol forcing) ==================
def twomey_sweep(backend_kind="mock", shots=SHOTS, n_ccn_list=(50, 100, 300,
                                                              1000, 3000),
                 duration=1800.0, dt=60.0, kappa=KAPPA):
    """Full Twomey experiment: effect of N_ccn [cm^-3] on cloud and rain.

    Split into the two channels of the first aerosol forcing:
      * TWOMEY (condensation): larger Nd -> larger total droplet surface area
        (Nd*r_bar ~ Nd^(2/3)) -> faster condensation -> more qc;
      * ALBRECHT (autoconversion): larger Nd -> smaller r_bar -> higher
        Q_CRIT and lower E(r_bar) -> precipitation suppression.
    """
    env = EnvProfile()
    rows = []
    for nccn in n_ccn_list:
        est = QuantumActivationEstimator(make_backend(backend_kind, shots), kappa)
        m = ParcelCloudModel(env, nccn * 1e4, est)
        t = 0.0
        while t < duration + 1e-9:
            m.step(dt)
            t += dt
        r_bar_peak = droplet_radius(m.max_qc, max(m.Nd_peak, 1.0))
        rows.append({"N_ccn_cm3": nccn, "LFC_m": (m.z_lfc or float("nan")),
                     "top_m": m.top_z, "w_max_ms": m.max_w,
                     "S_peak_pct": m.max_S * 100, "Nd_peak_cm3": m.Nd_peak / 1e4,
                     "r_bar_um": r_bar_peak * 1e6, "qc_max_gkg": m.max_qc * 1e3,
                     "cond_gkg": m.qc_from_cond * 1e3,          # Twomey channel
                     "auto_gkg": m.qc_from_auto * 1e3,          # Albrecht channel
                     "rain_gkg": m.rain_out * 1e3,
                     "mass_err_pct": m.mass_error_pct()})
    return rows


def print_twomey(rows):
    hdr = ("N_ccn [cm-3]  LFC [m]  top [m]  w_max [m/s]  S_peak [%]  Nd [cm-3] "
           "r_bar [um]  qc_max [g/kg]  cond [g/kg]  auto [g/kg]  rain [g/kg]  mass_err [%]")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print("%10d %9.0f %8.0f %10.2f %10.3f %10.1f %10.1f %13.3f "
              "%11.3f %11.3f %11.4f %11.2f"
            % (r["N_ccn_cm3"], r["LFC_m"], r["top_m"], r["w_max_ms"],
               r["S_peak_pct"], r["Nd_peak_cm3"], r["r_bar_um"],
               r["qc_max_gkg"], r["cond_gkg"], r["auto_gkg"],
               r["rain_gkg"], r["mass_err_pct"]))


def twomey_save(rows, csv_path="twomey_v8.csv", png_path="twomey_v8.png"):
    """Save CSV + 2x2 plot: S_peak, (Nd,r_bar), qc channels, rain and cloud top."""
    import csv as _csv
    keys = ["N_ccn_cm3", "LFC_m", "top_m", "w_max_ms", "S_peak_pct",
            "Nd_peak_cm3", "r_bar_um", "qc_max_gkg", "cond_gkg", "auto_gkg",
            "rain_gkg", "mass_err_pct"]
    with open(csv_path, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in keys})
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib unavailable — skipping the plot (CSV saved)")
        return None
    x = [r["N_ccn_cm3"] for r in rows]
    fig, ax = plt.subplots(2, 2, figsize=(11, 8))
    ax[0, 0].semilogx(x, [r["S_peak_pct"] for r in rows], "o-", color="tab:blue")
    ax[0, 0].set_title("S_peak vs N_ccn (supersaturation suppression)")
    ax[0, 0].set_xlabel("N_ccn [cm$^{-3}$]"); ax[0, 0].set_ylabel("S_peak [%]")
    ax[0, 1].semilogx(x, [r["Nd_peak_cm3"] for r in rows], "o-", color="tab:green",
                      label="Nd_peak")
    ax[0, 1].set_xlabel("N_ccn [cm$^{-3}$]"); ax[0, 1].set_ylabel("Nd_peak [cm$^{-3}$]")
    ax2 = ax[0, 1].twinx()
    ax2.semilogx(x, [r["r_bar_um"] for r in rows], "s--", color="tab:red",
                 label="r_bar @ max qc")
    ax2.set_ylabel("r_bar [um]")
    ax[0, 1].set_title("Nd_peak and r_bar vs N_ccn")
    h = 0.38
    xi = range(len(rows))
    ax[1, 0].bar([i - h/2 for i in xi], [r["cond_gkg"] for r in rows], h,
                 label="condensation (Twomey)", color="tab:cyan")
    ax[1, 0].bar([i + h/2 for i in xi], [r["auto_gkg"] for r in rows], h,
                 label="autoconversion (Albrecht)", color="tab:orange")
    ax[1, 0].plot(xi, [r["qc_max_gkg"] for r in rows], "k-o", lw=2,
                  label="qc_max")
    ax[1, 0].set_yscale("log")
    ax[1, 0].set_xticks(list(xi)); ax[1, 0].set_xticklabels([str(i) for i in x])
    ax[1, 0].set_xlabel("N_ccn [cm$^{-3}$]"); ax[1, 0].set_ylabel("[g/kg]")
    ax[1, 0].set_title("qc budget: Twomey/Albrecht channels")
    ax[1, 0].legend(fontsize=8)
    ax[1, 1].semilogx(x, [r["rain_gkg"] for r in rows], "o-", color="tab:brown",
                      label="rain (rain_out)")
    ax3 = ax[1, 1].twinx()
    ax3.semilogx(x, [r["top_m"] for r in rows], "^-", color="tab:purple",
                 label="cloud top")
    ax3.set_ylabel("top [m]")
    ax[1, 1].set_xlabel("N_ccn [cm$^{-3}$]"); ax[1, 1].set_ylabel("rain [g/kg]")
    ax[1, 1].set_title("Rain suppression and cloud top")
    fig.suptitle("WSM6-Q v8 — Twomey experiment (weighted CCN spectrum; first aerosol forcing)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(png_path, dpi=140)
    plt.close(fig)
    return png_path


# ===================== COMPARISON S_peak vs S_max(w, N_ccn) ================
def smax_comparison(backend_kind="mock", shots=SHOTS, kappa=KAPPA,
                    n_ccn_list=(50, 100, 300, 1000, 3000), duration=1200.0,
                    dt=60.0):
    """The model's prognostic S_peak (w from thermals) vs the reference curve
    S_max(w, N_ccn) at constant w — separates activation physics from forcing.
    Comparison made at w_at_Speak (the model's w when S_peak is reached).
    """
    env = EnvProfile()
    grid = smax_grid(env, n_ccn_list=n_ccn_list, kappa=kappa)
    rows = []
    for nccn in n_ccn_list:
        est = QuantumActivationEstimator(make_backend(backend_kind, shots), kappa)
        m = ParcelCloudModel(env, nccn * 1e4, est)
        t = 0.0
        while t < duration + 1e-9:
            m.step(dt)
            t += dt
        s_ref = smax_interp_row(grid["grid"][nccn], grid["w_list"], m.w_at_Speak)
        rows.append({"N_ccn_cm3": nccn, "S_peak_model_pct": m.max_S * 100,
                     "w_at_Speak_ms": m.w_at_Speak, "S_max_ref_pct": s_ref,
                     "diff_pct": (m.max_S * 100.0 - s_ref)})
    return grid, rows


def print_smax(grid, rows):
    ws = grid["w_list"]
    print("Reference S_max(w, N_ccn) [%] — classical, constant w:")
    hdr = "N_ccn [cm-3]" + "".join("%10.0f" % w for w in ws)
    print(hdr); print("-" * len(hdr))
    for nccn in grid["n_ccn_list"]:
        print("%12d" % nccn + "".join("%10.4f" % v for v in grid["grid"][nccn]))
    print()
    hdr = ("N_ccn [cm-3]  S_peak model [%]  w@S_peak [m/s]  S_max ref(w) [%]  "
           "roznica [pp]")
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print("%12d %16.4f %15.3f %17.4f %12.4f"
              % (r["N_ccn_cm3"], r["S_peak_model_pct"], r["w_at_Speak_ms"],
                 r["S_max_ref_pct"], r["diff_pct"]))


def smax_plot(grid, rows, png_path="smax_v8.png"):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib unavailable — skipping the plot")
        return None
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for nccn in grid["n_ccn_list"]:
        ax.plot(grid["w_list"], grid["grid"][nccn], "o-", label="N_ccn=%d" % nccn)
    for r in rows:
        ax.plot([r["w_at_Speak_ms"]], [r["S_peak_model_pct"]], "kx", ms=10, mew=2)
    ax.plot([], [], "kx", ms=10, mew=2, label="model S_peak (w from thermals)")
    ax.set_xlabel("w [m/s]"); ax.set_ylabel("S_max / S_peak [%]")
    ax.set_title("WSM6-Q v8 — reference curve S_max(w, N_ccn) vs model S_peak")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(png_path, dpi=140)
    plt.close(fig)
    return png_path


# ===================== SELFTEST v8 =========================================
def selftest():
    global N_IDX, TH_NAMES
    _saved = (N_IDX, TH_NAMES)
    N_IDX = 4
    # selftest: N_IDX=4 (16 bins) — same naming convention as in main()
    TH_NAMES = ["th" + format(k, "x") for k in range(2 ** N_IDX)]
    try:
        print("=" * 72)
        print("SELFTEST v8 — weighted CCN spectrum + parcel(w from thermals) + A&G + IAA/QAE + Twomey")
        print("=" * 72)
        ok_all = True

        # [T1] m=0, Koehler oracle: P(a=1) == WEIGHTED MEAN sum w_i f_i (v8 core)
        probs = activation_probabilities(1.002, 295.0)
        angles = encode_from_probs(probs)
        w_sp = aerosol_weights(2 ** N_IDX)
        f_bar = sum(wi * pi for wi, pi in zip(w_sp, probs))
        p0 = ancilla_prob(build_iaa_ops(0, w_sp), angles)
        ok1 = abs(p0 - f_bar) < 1e-9
        print("[T1] IAA m=0 (weighted state): P(a=1)=%.10f vs sum(w_i f_i)=%.10f  %s"
              % (p0, f_bar, "OK" if ok1 else "FAIL"))

        # [T2] IAA diffuser with reflection S_phi about the WEIGHTED STATE: uniform oracle
        f_u = 0.30
        th_u = [2.0 * math.asin(math.sqrt(f_u))] * (2 ** N_IDX)
        beta = math.asin(math.sqrt(f_u))
        maxdiff = max(abs(ancilla_prob(build_iaa_ops(m, w_sp), th_u)
                          - math.sin((2 * m + 1) * beta) ** 2) for m in MS)
        ok2 = maxdiff < 1e-9
        print("[T2] Grover diffuser: MAXDIFF=%.2e  %s" % (maxdiff, "OK" if ok2 else "FAIL"))

        # [T3] QAE decoder recovers f
        p_by_m = {m: math.sin((2 * m + 1) * beta) ** 2 for m in MS}
        f_hat = decode_fbar(p_by_m)
        ok3 = abs(f_hat - f_u) < 1e-3
        print("[T3] QAE decoder: f_hat=%.6f vs f=%.6f  %s" % (f_hat, f_u, "OK" if ok3 else "FAIL"))

        # [T4] MCX/MCZ decomposition == native version (full state vector)
        nq = n_qubits_native()
        preps = [[("h", j) for j in range(nq)],
                 [("h", j) for j in range(nq)] + [("x", 0)]]
        maxd = 0.0
        for prep in preps:
            ctrl, tgt = list(range(1, 1 + N_IDX)), work_q()
            s_nat = simulate(prep + [("mcx", ctrl, tgt)], [], nq)
            dec_ops, dnq = decompose_ops(prep + [("mcx", ctrl, tgt)])
            s_dec = simulate(dec_ops, [], dnq)
            maxd = max(maxd, max(abs(s_nat[st] - s_dec[st]) for st in range(2 ** nq)))
            ctrlz = list(range(nq))
            s_nat2 = simulate(prep + [("mcz", ctrlz)], [], nq)
            dec_ops2, dnq2 = decompose_ops(prep + [("mcz", ctrlz)])
            s_dec2 = simulate(dec_ops2, [], dnq2)
            maxd = max(maxd, max(abs(s_nat2[st] - s_dec2[st]) for st in range(2 ** nq)))
        ok4 = maxd < 1e-9
        print("[T4] MCX/MCZ decomposition (full state): maxdiff=%.1e  %s" % (maxd, "OK" if ok4 else "FAIL"))

        # [T4b] CRY decomposition (multiple controls) == native version
        #     — the Toffoli ladder used in the weighted-state prep on CUDA-Q
        maxd_cry = 0.0
        for ctrl in ([2], [1, 3], [2, 3], [1, 2, 3]):
            ops_cry = [("cry", list(ctrl), 4, 0.7)]
            s_nat_c = simulate(ops_cry, [], nq)
            dec_c, dnq_c = decompose_ops(ops_cry)
            s_dec_c = simulate(dec_c, [], dnq_c)
            maxd_cry = max(maxd_cry, max(abs(s_nat_c[st] - s_dec_c[st]) for st in range(2 ** nq)))
        ok4b = maxd_cry < 1e-9
        print("[T4b] CRY decomposition (full state): maxdiff=%.1e  %s" % (maxd_cry, "OK" if ok4b else "FAIL"))

        # [T5] Koehler: S_crit decreasing with r_dry, realistic for CCN
        Sc = {rd: kohlert_critical_supersat(rd, 295.0) for rd in (20e-9, 100e-9, 500e-9)}
        ok5 = Sc[20e-9] > Sc[100e-9] > Sc[500e-9] and 1.0 < Sc[100e-9] < 1.01
        print("[T5] Koehler: S_crit(20/100/500nm)=%.4f/%.4f/%.4f  %s"
              % (Sc[20e-9], Sc[100e-9], Sc[500e-9], "OK" if ok5 else "FAIL"))

        # [T6] thermals: LFC in the BL, CAPE>0, CIN>=0, Gamma_d ~ 9.8 K/km,
        #     environment unsaturated at the cap base (profile consistency)
        env = EnvProfile()
        cape, cin, lfc = cape_cin(env)
        T600, T900 = env.T(600.0), env.T(900.0)
        lapse = (T600 - T900) / 300.0 * 1e3          # K/km w neutralnej BL
        rh_cap = env.qv(env.z_cap0 - 1.0) / q_sat(env.T(env.z_cap0 - 1.0),
                                                  pressure(env.z_cap0 - 1.0)) * 100.0
        ok6 = (lfc is not None and 800 < lfc < 2200 and cape > 200.0 and cin >= 0.0
               and 8.5 < lapse < 11.0 and rh_cap < 95.0)
        print("[T6] profil: LFC=%.0f m, CAPE=%.0f J/kg, CIN=%.1f J/kg, Gamma_d=%.2f K/km, "
              "RH(cap base)=%.0f%%  %s" % (lfc or -1, cape, cin, lapse, rh_cap,
                                           "OK" if ok6 else "WARN"))

        # [T7] vapor competition: larger N_ccn -> lower S_peak (A&G)
        est_lo = QuantumActivationEstimator(MockBackend(shots=1024))
        est_hi = QuantumActivationEstimator(MockBackend(shots=1024))
        m_lo = ParcelCloudModel(env, 50e3, est_lo)
        m_hi = ParcelCloudModel(env, 3000e3, est_hi)
        for _ in range(1800):
            m_lo.step(1.0); m_hi.step(1.0)
        ok7 = (m_hi.max_S < m_lo.max_S and m_hi.Nd_peak <= 3000e3 + 1e-9
               and m_lo.Nd_peak > 0.0 and m_hi.max_S > 0.0)
        print("[T7] A&G competition: S_peak(50cm-3)=%.3f%% vs (3000cm-3)=%.3f%%; "
              "Nd(3000)<N_a  %s"
              % (m_lo.max_S * 100, m_hi.max_S * 100, "OK" if ok7 else "WARN"))

        # [T8] Twomey: at the same qc, larger Nd -> smaller autoconversion flux
        f_low = autoconversion_flux(1.0e-3, 9e4)
        f_high = autoconversion_flux(1.0e-3, 2.7e6)
        ok8 = 0.0 < f_high < f_low
        print("[T8] Twomey: flux(qc=1g/kg; Nd=9e4)=%.2e > (Nd=2.7e6)=%.2e  %s"
              % (f_low, f_high, "OK" if ok8 else "FAIL"))

        # [T9] mass balance over a full parcel run (600 s)
        est = QuantumActivationEstimator(MockBackend(shots=1024))
        m = ParcelCloudModel(env, 100e3, est)
        for _ in range(200):
            m.step(3.0)
        err = m.mass_error_pct()
        ok9 = err < 2.0
        print("[T9] mass balance (600 s): err=%.3f%%  %s" % (err, "OK" if ok9 else "WARN"))

        # [T10] v8: weighted log-normal CCN spectrum + monotonicity of S_max(N_ccn)
        i_mode = max(range(len(w_sp)), key=lambda k: w_sp[k])
        rds_t10 = aerosol_spectrum(2 ** N_IDX)
        step_ln = math.log(R_MAX / R_MIN) / (2 ** N_IDX - 1)
        ok_w = (abs(sum(w_sp) - 1.0) < 1e-12 and all(x > 0.0 for x in w_sp)
                and abs(math.log(rds_t10[i_mode] / R_MODE)) <= step_ln / 2.0 + 1e-12)
        fw10 = sum(wi * pi for wi, pi in zip(w_sp, probs))
        fu10 = sum(probs) / len(probs)
        ok_w = ok_w and abs(fw10 - fu10) > 1e-4    # particle mean != radius-bin mean
        s_lo = smax_reference(env, 100e4, 3.0, duration=900.0)["S_max"]
        s_hi = smax_reference(env, 3000e4, 3.0, duration=900.0)["S_max"]
        ok_smax = (s_lo > 0.0 and s_hi < s_lo)
        ok10 = ok_w and ok_smax
        print("[T10] CCN weights: sum(w)=1, peak at r_mode; weighted mean %.4f != uniform %.4f; "
              "S_max(100cm-3)=%.3f%% > S_max(3000cm-3)=%.3f%%  %s"
              % (fw10, fu10, s_lo * 100.0, s_hi * 100.0, "OK" if ok10 else "FAIL"))

        # [T11] weighted-state prep: |psi_i|^2 == w_i for ALL bins
        #     — the guarantee that the quantum part realizes the state sum sqrt(w_i)|i>
        psi_t11 = simulate(build_prep_ops(w_sp), [], n_qubits_native())
        maxd11 = 0.0
        for i in range(2 ** N_IDX):
            st = i << 1          # anc=0, work=0; idx bits from q[1] (LSB)
            maxd11 = max(maxd11, abs(abs(psi_t11[st]) ** 2 - w_sp[i]))
        ok11 = maxd11 < 1e-12
        print("[T11] CCN spectrum prep: max |P(i) - w_i|=%.2e (N=%d bins)  %s"
              % (maxd11, 2 ** N_IDX, "OK" if ok11 else "FAIL"))

        ok_all = all([ok1, ok2, ok3, ok4, ok4b, ok5, ok8, ok10, ok11])
        print("-" * 72)
        print("SELFTEST:", "ALL PASSED" if ok_all else "FAILURES PRESENT (T6/T7/T9 = WARN)")
        return ok_all
    finally:
        N_IDX, TH_NAMES = _saved


# ===================== MAIN ================================================
def main():
    global N_IDX, TH_NAMES, BACKEND, R_MODE, SIGMA_G
    ap = argparse.ArgumentParser(
        description="WSM6-Q v8: parcel model + A&G-inspired activation + weighted CCN spectrum + Twomey")
    ap.add_argument("--backend", choices=["auto", "cudaq", "mock"], default="auto")
    ap.add_argument("--shots", type=int, default=SHOTS)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--n-idx", type=int, default=N_IDX)
    ap.add_argument("--kappa", type=float, default=KAPPA,
                    help="hygroscopicity multiplier on the osmotic term (1.0=full sea salt)")
    ap.add_argument("--r-mode", type=float, default=80.0,
                    help="modal radius of the log-normal CCN spectrum [nm] (default 80)")
    ap.add_argument("--sigma-g", type=float, default=1.7,
                    help="geometric standard deviation of the CCN spectrum (default 1.7)")
    ap.add_argument("--nccn", type=float, default=100.0,
                    help="CCN number [cm^-3] (default 100)")
    ap.add_argument("--w0", type=float, default=0.5, help="triggering vertical velocity [m/s]")
    ap.add_argument("--drag-tau", type=float, default=40.0, help="drag timescale [s]")
    ap.add_argument("--duration", type=float, default=1800.0)
    ap.add_argument("--dt", type=float, default=60.0)
    ap.add_argument("--twomey", action="store_true",
                    help="full Twomey experiment: 50..3000 cm^-3 + CSV/PNG")
    ap.add_argument("--smax", action="store_true",
                    help="reference curve S_max(w, N_ccn) vs prognostic S_peak")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    N_IDX = args.n_idx
    R_MODE = args.r_mode * 1e-9
    SIGMA_G = args.sigma_g
    TH_NAMES = ["th" + format(k, "x") for k in range(2 ** N_IDX)]
    BACKEND = make_backend(args.backend, args.shots)

    if args.twomey:
        print("=" * 78)
        print("WSM6-Q v8 — FULL TWOMEY EXPERIMENT (1st aerosol forcing)")
        print("backend: %s | N=%d spectrum bins | κ=%.2f" % (args.backend, 2 ** N_IDX, args.kappa))
        print("CCN spectrum: log-normal r_mode=%.0f nm sigma_g=%.2f -> particle weights, <f> = sum w_i f_i"
              % (R_MODE * 1e9, SIGMA_G))
        print("=" * 78)
        rows = twomey_sweep(args.backend, args.shots, duration=args.duration,
                            dt=args.dt, kappa=args.kappa)
        print_twomey(rows)
        png = twomey_save(rows)
        if png:
            print("Saved: twomey_v8.csv and %s" % png)
        return

    if args.smax:
        print("=" * 78)
        print("WSM6-Q v8 — S_max(w, N_ccn): classical (constant w) vs prognostic model")
        print("backend: %s | κ=%.2f | CCN spectrum: r_mode=%.0f nm sigma_g=%.2f"
              % (args.backend, args.kappa, R_MODE * 1e9, SIGMA_G))
        print("=" * 78)
        grid, rows = smax_comparison(args.backend, args.shots, kappa=args.kappa,
                                     duration=args.duration, dt=args.dt)
        print_smax(grid, rows)
        png = smax_plot(grid, rows)
        if png:
            print("Saved: %s" % png)
        return

    env = EnvProfile()
    cape, cin, lfc = cape_cin(env)
    print("=" * 78)
    print("WSM6-Q v8 — parcel model: A&G-inspired prognostic activation + weighted CCN spectrum")
    print("(N=%d bins; <f_i> = sum w_i f_i — particle mean, quantum state sum sqrt(w_i)|i>)"
          % (2 ** N_IDX,))
    print("backend: %s | shots/measurement: %d | κ=%.2f | N_ccn=%.0f cm^-3"
          % (args.backend, args.shots, args.kappa, args.nccn))
    print("-" * 78)
    print("Environment profile: SA 0-%.0f m (+%.1f K at the surface) | BL theta=%.1f K qv=%.2f g/kg"
          % (env.z_sa, env.dth_sa, env.theta_bl, env.qv_bl * 1e3))
    print("  cap %.0f-%.0f m (+%.1f K inversion) | FT stable (%.0f K/km)"
          % (env.z_cap0, env.z_cap1, env.dth_cap * (env.z_cap1 - env.z_cap0),
             env.dth_ft * 1e3))
    print("CAPE=%.0f J/kg  CIN=%.1f J/kg  LFC~%.0f m   -> w(t) from buoyancy, drag tau=%.0f s"
          % (cape, cin, lfc or -1, args.drag_tau))

    # --- Koehler physics on the spectrum ---
    T0 = env.T(100.0)
    rds = aerosol_spectrum(2 ** N_IDX)
    Scs = [kohlert_critical_supersat(rd, T0, args.kappa) for rd in rds]
    print("Aerosol: r_dry %.0f-%.0f nm | S_crit min=%.4f max=%.4f"
          % (rds[0] * 1e9, rds[-1] * 1e9, min(Scs), max(Scs)))
    print("CCN spectrum: log-normal r_mode=%.0f nm sigma_g=%.2f (particle weights w_i)"
          % (R_MODE * 1e9, SIGMA_G))

    # --- quantum estimator + model ---
    est = QuantumActivationEstimator(BACKEND, args.kappa)

    model = ParcelCloudModel(env, args.nccn * 1e4, est, w0=args.w0,
                             drag_tau=args.drag_tau)

    print("\n t [s]   z [m]  w [m/s]  T [K]  S [%]  qv qc qr [g/kg]  Nd [cm-3]  rain [g/kg]")
    t = 0.0
    while t < args.duration + 1e-9:
        s = model.state()
        print("%6.0f %7.0f %8.2f %7.2f %7.4f %6.3f %5.3f %5.3f %9.1f %10.4f"
              % (s["t_s"], s["z_m"], s["w_ms"], s["T_K"], s["S_pct"],
                 s["qv_gkg"], s["qc_gkg"], s["qr_gkg"], s["Nd_cm3"], s["opad_gkg"]))
        model.step(args.dt)
        t += args.dt

    # --- quantum report (full QAE decoding at S_peak) ---
    rep = est.qae_report(1.0 + model.max_S, model.T)
    print("-" * 78)
    print("Run: LFC=%.0f m | cloud top=%.0f m | w_max=%.2f m/s | S_peak=%.3f%%"
          % (model.z_lfc or -1, model.top_z, model.max_w, model.max_S * 100))
    print("Nd_peak=%.1f cm^-3 (from N_ccn=%.0f) | r_bar at max qc: %.1f um | qc_max=%.3f g/kg"
          % (model.Nd_peak / 1e4, args.nccn,
             droplet_radius(model.max_qc, max(model.Nd_peak, 1.0)) * 1e6,
             model.max_qc * 1e3))
    print("Rainout: %.4f g/kg | mass balance: err=%.3f%%" % (model.rain_out * 1e3, model.mass_error_pct()))
    print("-" * 78)
    print("QUANTUM (weighted-mean estimator <f_i> = sum w_i f_i over the CCN spectrum —")
    print("quantum state sum sqrt(w_i)|i>, IAA m=0, P(a=1); QAE decoding is DIAGNOSTIC ONLY):")
    print("  estimator calls in the loop: %d | QAE report at S_peak:" % est.n_calls)
    for m in [0] + list(MS):
        print("    p(m=%d)=%.6f" % (m, rep["p_by_m"][m]))
    print("  f_exact(weighted, particle mean)=%.6f   [for comparison, v7 radius-bin mean: %.6f]"
          % (rep["f_exact"], rep["f_mean_radius"]))
    print("  f(m=0 quantum)=%.6f   f(QAE-decoded)=%.6f"
          % (rep["p_by_m"][0], rep["f_qae"]))


if __name__ == "__main__":
    main()
