# WSM6-Q — Quantum-Assisted Convective Cloud Model (v8)

**A one-dimensional parcel model of a convective cloud with classical thermodynamics
and microphysics, in which exactly one component is quantum: an estimator of the mean
activated fraction ⟨fᵢ⟩ over the aerosol (CCN) spectrum.**

Everything else — pseudo-adiabatic parcel ascent, buoyancy feedback, A&G-inspired
prognostic activation, condensation, autoconversion and rainout — is classical
convective physics, exactly as in real WRF/ICON/IFS schemes. The quantum accelerator
(if one existed) would plug into precisely the spot this model highlights: the expensive
averaging over the CCN spectrum.
---

![](./img/head.png)

## What this project does

WSM6-Q is a one-dimensional **warm-rain parcel model** of a single convective cloud element. It
integrates, second by second, the vertical motion and thermodynamics of an air parcel rising
through a prescribed environment, coupled to prognostic cloud microphysics:

- **Thermodynamics (classical).** Pseudo-adiabatic ascent; buoyancy from the virtual-potential-
  temperature difference `B = g(θ_vp − θ_ve)/θ_ve`; and an effective drag law `dw/dt = B − εw`
  that closes the feedback loop *latent heat → T → buoyancy → w → supersaturation S*.
- **CCN activation (classical scheme + quantum mean).** A log-normal aerosol spectrum of
  N = 2^N_IDX dry-radius bins is activated with κ-Köhler theory in an A&G-inspired differential
  form. The single number the microphysics needs — the *activated fraction*
  f(S,T) = ⟨fᵢ⟩, the mean over the spectrum — is computed by a **quantum amplitude estimator**
  (the only quantum call in the model).
- **Microphysics (classical, driven by N_d = N_ccn·f).** Condensation (Twomey channel),
  autoconversion with droplet-size dependence (Albrecht channel), accretion and rainout.

**Inputs:** an environmental profile (θ, qv vs z) + CCN number concentration N_ccn + spectrum
shape (r_mode, σ_g). **Outputs:** the parcel trajectory and cloud state over time — peak
supersaturation S_peak, droplet concentration N_d, mean radius r̄, condensed water q_c, rain q_r:
a miniature of the first-aerosol-forcing (Twomey/Albrecht) response that full 3-D models
(WRF, ICON, IFS) compute with bulk schemes.

The goal is not to beat those models but to isolate and *quantum-accelerate the single expensive
average* — ⟨fᵢ⟩ over the CCN spectrum — that every one of them performs at each activation step.

---

## What changed in v8 (the only scientific change)

In v7 and earlier the activated fraction was averaged **uniformly over radius bins**

    ⟨f⟩ = (1/N) Σᵢ fᵢ

which gave a 20 nm bin and a 500 nm bin equal weight, even though in the atmosphere
the extreme bins hold far fewer particles than the vicinity of the mode.

v8 replaces this with the **particle-population weighted mean** over a log-normal CCN
spectrum:

    ⟨f⟩ = Σᵢ wᵢ fᵢ / Σᵢ wᵢ,   wᵢ ∝ exp( −[ln(rᵢ/r_mode)]² / (2 ln²σ_g) )

The quantum state is no longer the uniform superposition `(1/√N) Σᵢ |i⟩` but

    |ψ⟩ = Σᵢ √wᵢ |i⟩

— the amplitudes encode the real aerosol spectrum. Measuring the ancilla then returns
the physically correct mean directly: `P(a=1) = Σᵢ wᵢ fᵢ`.

> At S = 1.002, T = 295 K the particle-weighted mean is **0.8966** while the old
> radius-bin mean is **0.8126** — a ~10 % shift that changes the droplet concentration
> N_d and hence the whole microphysics downstream.

![CCN spectrum](img/ccn_spectrum_v8.png)

*Left: log-normal CCN particle weights wᵢ (blue) and the Köhler critical supersaturation
S_crit(i) (red) over 64 dry-radius bins. Right: the per-bin activated fraction fᵢ(S,T);
the v8 particle-weighted mean (blue) vs the v7 uniform radius-bin mean (grey dashed).*

---

## Physics pipeline

```
 Thermodynamics (CLASSICAL)
 |-- environment profile θ_env(z), qv_env(z)  ->  CAPE / CIN / LFC
 |-- parcel model: dT/dt (pseudo-adiabat), z(t), w(t)
 |-- buoyancy B = g (θ_v,p − θ_v,env)/θ_v,env
 |-- dw/dt = B − ε w   (effective drag, τ_drag)  ->  feedback loop: latent heat → T → B → w → S

 CCN activation (CLASSICAL + quantum mean estimator)
 |-- log-normal aerosol spectrum, N = 2^N_IDX dry-radius bins
 |-- κ-Köhler: S_crit(i), r_crit(i)   [Petters & Pruppacher]
 |-- A&G-inspired prognostic activation (Abdul-Razzak & Ghan 1995):
 |     dS/dt = adiabatic supply(z, w) − vapor competition(S, N_d, r̄)
 |   irreversible activation: a bin activates once S > S_crit(i)
 |-- f(S,T) = ⟨fᵢ⟩ — THE ACTIVATED-FRACTION MEAN — THE ONLY QUANTUM SPOT
 |     (v8: particle-weighted ⟨fᵢ⟩ = Σ wᵢ fᵢ; state Σ √wᵢ |i⟩; IAA m=0 in the loop)
 |-- N_d = N_ccn · f  ->  cloud droplet number concentration (prognostic)

 Cloud microphysics (CLASSICAL, dependence on N_d → Twomey effect)
 |-- condensation (Fuchs–Stevens, bulk: dq_c/dt ~ S·N_d·r̄)
 |     -> TWOMEY channel: larger N_d = more total droplet surface area = faster growth
 |-- autoconversion: threshold Q_CRIT(N_d) + collision efficiency E(r̄)
 |     -> ALBRECHT channel: larger N_d = less rain (precipitation suppression)
 |-- accretion (q_r collects q_c), sedimentation / rainout of q_r
```

---

## The quantum component — precisely what it is (and is not)

- **Estimator:** Iterative Amplitude Amplification (IAA) at m = 0, shot-based. The
  ancilla probability `P(a=1)` equals the spectrum mean `Σᵢ wᵢ fᵢ`.
- **State preparation:** recursive amplitude encoding (MSB→LSB) builds
  `|ψ⟩ = Σᵢ √wᵢ |i⟩`; cost is N−1 rotations + O(N) X gates. Verified by self-test [T11]:
  max |P(i) − wᵢ| < 1e−12 across all bins.
- **Decoding:** full QAE decoding (m = 0…3) is used **only for diagnostics/verification**
  and does not speed up the model.
- **Honest scope:** this is a *spectrum-mean estimator*, not a speedup of regression or
  microphysics. Its advantage over classical summation applies in an oracle model where
  each fᵢ is expensive to compute (the full version uses an arithmetic oracle that
  computes S_crit(i) from |i⟩).

---

## What runs in CUDA-Q (the implementation)

The quantum part is a shot-based **Iterative Amplitude Amplification (IAA)** estimator of
⟨fᵢ⟩ = Σᵢ wᵢ fᵢ. Kernels are built with the CUDA-Q **builder API** (`cudaq.make_kernel()`), not
generated as text, and run on the simulator backend; the same code targets hardware.

```
┌──────────────────────────────────────┐
│ state prep                           │
│ |psi> = SUM_i sqrt(w_i)|i>           │
│ (N-1 controlled-RY + O(N) X gates)   │
└───────────────────┬──────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│ oracle O_f  (applied per bin i)      │
│   X on the zero bits of i            │
│   MCX(idx -> work)                   │
│   CX(work->anc); RY(-sign*theta_i/2) │
│   CX(work->anc); RY(+sign*theta_i/2) │
│   MCX(idx -> work)      [uncompute]  │
└───────────────────┬──────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│ m x Grover iteration (m = 1..3)      │
│   S_psi . O_f^dagger . S_G           │
│   (diagnostics / decoding only)      │
└──────────────────────────────────────┘
        │
        ▼
   measure ancilla q[0]
   P(a=1) = <f_i> = SUM_i w_i f_i

 registers (N_IDX+2):  q[0]=ancilla | q[1..N_IDX]=index |i> | q[N_IDX+1]=work
```

### Qubit layout (N_IDX + 2 qubits)

| Qubit | Role |
|:---|:---|
| `q[0]` | ancilla — **measured**; P(a=1) is the estimator output |
| `q[1..N_IDX]` | index register, LSB = q[1]; holds \|i⟩ for bin i |
| `q[N_IDX+1]` | work qubit (clean before and after each oracle call) |

### Circuit (`build_iaa_ops`)

- **State preparation** — recursive amplitude encoding (MSB→LSB): N−1 controlled-RY rotations +
  O(N) X gates build \|ψ⟩ = Σᵢ √wᵢ \|i⟩. The CCN weights wᵢ are *baked constants* (the spectrum
  shape is fixed at compile time). Verified by self-test [T11].
- **Oracle O_f** — for each bin i, a phase-kickback gadget: X on the zero bits of i, an
  MCX(idx→work), then `CX(work→anc); RY(−sign·θᵢ/2); CX(work→anc); RY(+sign·θᵢ/2)` on the ancilla,
  and uncompute. The θᵢ = 2 asin √fᵢ are **runtime float kernel arguments** (2^N_IDX of them), so
  one compiled kernel is reused for any S,T by passing new angles.
- **Grover iterations (m = 1..3, diagnostics only)** — O_f · S_ψ · O_f† · S_G, with the reflection
  about \|ψ⟩ and the diffuser `H·X·MCZ(all)·X·H`.

### Gate set & multi-control gates

Single-qubit: H, X, Z, RY. Multi-qubit: CNOT, **MCX** (multi-control X), **MCZ** (multi-control
Z) and **multi-control CRY**. In the builder API `cx`/`cz`/`cry` accept a *list of control
qubits*, so MCX/MCZ/multi-control-CRY are emitted natively — no Toffoli decomposition on this
path. The `mock` backend and self-tests [T4/T4b] separately verify that the explicit Barenco-ladder
decomposition is equivalent.

### Sampling & scaling

Each estimate draws `--shots` samples (`cudaq.sample(kernel, *angles, shots_count=shots)`) and
reports the fraction with ancilla = 1. Resolution is set by `--n-idx`: bins = 2^N_IDX (default
N_IDX = 6 → 64 bins); kernels are compiled once per (N_IDX, r_mode, σ_g) and cached. The `mock`
backend is an exact state-vector simulator of the *same* native ops with binomial shot noise, used
as the numerical reference.

---

## Results

### 1. Twomey experiment — the first aerosol forcing (`--twomey`)

Sweeping the CCN number concentration from 50 to 3000 cm⁻³ through the full parcel model:

| N_ccn [cm⁻³] | S_peak [%] | N_d,peak [cm⁻³] | r̄ [µm] | q_c,max [g/kg] | condensation [g/kg] | autoconversion [g/kg] | rain [g/kg] |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 50   | 0.229 | 45.0  | 80.9 | 0.996 | 2.591 | 2.277 | 0.0616 |
| 100  | 0.169 | 80.4  | 66.9 | 1.007 | 2.591 | 2.274 | 0.0612 |
| 300  | 0.097 | 182.0 | 52.0 | 1.067 | 2.591 | 2.249 | 0.0585 |
| 1000 | 0.050 | 414.8 | 44.2 | 1.497 | 2.591 | 1.842 | 0.0384 |
| 3000 | ~0    | 706.1 | 43.1 | 2.370 | 2.591 | 0.539 | **0.0042** |

![Twomey](img/twomey_v8.png)

Reading the figure:
- **Supersaturation suppression:** more CCN → each droplet grows less → S_peak collapses
  from 0.23 % to ~0 (top-left).
- **Droplet size:** N_d rises while the mean radius r̄ falls from 81 µm to 43 µm
  (top-right) — the classic A&G trade-off.
- **Two aerosol-forcing channels** (bottom-left): total condensation (Twomey) stays roughly
  flat, but autoconversion (Albrecht) collapses as r̄ shrinks below the collision threshold.
- **Rain suppression** (bottom-right): rain falls from 0.062 to 0.004 g/kg — a ~15× reduction —
  while the cloud top barely moves. This is the first aerosol forcing in its textbook form.

### 2. Activation physics vs thermal forcing (`--smax`)

The reference curve S_max(w, N_ccn) is computed by classical A&G integration at **constant w**
(no buoyancy/drag), isolating the pure activation response. The model's prognostic S_peak
(w from thermals) is then compared against it at w_at_Speak:

![S_max](img/smax_v8.png)

The black ✕ markers (prognostic S_peak) lie on the classical reference curves for each N_ccn,
confirming that the differential A&G-inspired scheme reproduces the asymptotic activation
physics once the thermal forcing is accounted for.

---

## File layout

| File | Role |
|:---|:---|
| `wsm6_quantum_v8.py` | **The model** — parcel + A&G-inspired activation + weighted CCN spectrum + Twomey/Albrecht microphysics + IAA/QAE estimator. Self-contained, no VQE. |
| `vqe_demo.py` | Standalone VQE demo (H₂O–aerosol Ising clusters, 4 qubits) — separated out per the reviewer decision; **not** part of the model. |
| `quantum.py`, `wsm6_quantum_v1…v7.py` | Historical / reference snapshots of earlier iterations. |
| `img/` | Figures referenced by this README. |

---

## Running

```bash
pip install numpy matplotlib        # core (CPU, "mock" backend)
pip install cudaq                   # optional: real CUDA-Q backend for the IAA circuit

python wsm6_quantum_v8.py --selftest              # T1…T11 verification suite
python wsm6_quantum_v8.py --backend mock          # full parcel run (CPU state-vector simulator)
python wsm6_quantum_v8.py --backend cudaq         # IAA on CUDA-Q
python wsm6_quantum_v8.py --twomey                # full Twomey experiment -> twomey_v8.csv + .png
python wsm6_quantum_v8.py --smax                  # S_max(w, N_ccn) reference vs prognostic S_peak

# tune the aerosol / forcing
python wsm6_quantum_v8.py --nccn 3000 --duration 2400
python wsm6_quantum_v8.py --r-mode 80 --sigma-g 1.7     # log-normal CCN spectrum
```

Key CLI options: `--backend {auto,cudaq,mock}`, `--shots`, `--n-idx` (spectrum bins = 2^N_IDX),
`--kappa` (hygroscopicity), `--r-mode` / `--sigma-g` (CCN spectrum shape), `--nccn`, `--w0`,
`--drag-tau`, `--duration`, `--dt`.

---

## Verification (`--selftest`)

The suite checks the quantum and classical pieces independently:

| Test | Checks |
|:---|:---|
| T1  | IAA m=0 on the weighted state: P(a=1) = Σ wᵢ fᵢ (the v8 core) |
| T2  | Grover/QAE diffuser reflection about the weighted state (m = 1,2,3) |
| T3  | QAE decoder recovers f from {p(m)} |
| T4 / T4b | MCX/MCZ and multi-control CRY decompositions == native version on the full state vector (protects the CUDA-Q backend) |
| T5  | Köhler: S_crit decreases with r_dry; realistic CCN values |
| T6  | Environment profile: LFC in the BL, CAPE > 0, Γ_d ≈ 9.5 K/km, cap-base RH < 95 % |
| T7  | A&G competition: larger N_ccn → lower S_peak; N_d < N_a |
| T8  | Twomey: at fixed q_c, larger N_d → smaller autoconversion flux |
| T9  | Mass balance over a full parcel run (err ≪ 2 %) |
| T10 | CCN weights: Σw = 1, peak at r_mode; weighted mean ≠ radius-bin mean; S_max(100) > S_max(3000) |
| T11 | Amplitude encoding: \|ψᵢ\|² = wᵢ for **all** bins (max error < 1e−12) |

Latest run: **ALL PASSED.**

---

## Honest limitations

- A single, one-dimensional parcel — no horizontal transport, turbulence or advection; drag is
  an effective parameter (τ_drag), not LES.
- Activation is a scheme *inspired by* Abdul-Razzak & Ghan (1995) in differential form
  (S as the state variable), not the asymptotic formula S_max(N_a, w); the reference curve is
  computed separately (`--smax`) for comparison. Requires dt_sub = 0.5 s.
- Autoconversion is a parameterization (threshold + E(r̄)), not a spectral collision model.
- The quantum part estimates the **weighted mean** ⟨fᵢ⟩ = Σ wᵢ fᵢ (log-normal particle weights;
  state Σ √wᵢ |i⟩; IAA m=0). It is a spectrum-mean estimator, not a speedup of regression /
  microphysics; QAE decoding is diagnostic only.

---

## References

- Abdul-Razzak, H. & Ghan, S. J. (1995). A parameterization for activation of aerosols as cloud
  condensation nuclei. *Q. J. R. Meteorol. Soc.* **121**, 67–83.
- Petters, M. D. & Pruppacher, H. R. (2007). A revision of the Köhler theory for water activity
  and curvature... *J. Atmos. Sci.* **64**, 295–308.
- Twomey, S. (1959); Albrecht, B. A. (1989). The first aerosol forcing.
- Grover (1998); amplitude amplification and quantum amplitude estimation (QAE).
