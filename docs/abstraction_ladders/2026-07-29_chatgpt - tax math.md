# Average-cost approximations

**Date:** 2026-08-04
**Source:** chatgpt.com

---

### **You**

Can you help me figure out some equations, for calculating the numbers of tasks that an abstraction ladder runs on during each wake cycle? This is in program synthesis with library learning.

Curriculum tax:
- Hmm.
- This splits into:
    1. Tax for search costs on tasks already previously solved (lower-rung tasks).
    2. Tax for search costs on tasks not “intended” to be solved (higher-rung tasks).
- We’re able to run ladders in 2 modes:
    1. Optimal curriculum
        - At each wake, search runs on only the tasks for the next rung.
    2. Full curriculum
- A single run on one task must be one of:
    1. Lower-rung task
        - The task is able to be solved (given the library and config).
        - The search does NOT have to run to exhaustion (depends on early stopping settings).
        - More recently learned abstractions have an impact:
            - More abstractions added to the pool: That’s a Higher search cost factor (via breadth, via starting primitive count)
            - If any more recent abstractions help solve the task more efficiently: That’s a Lower search cost factor.
    2. Current-rung task
        - The task is able to be solved (given the library and config).
    3. Higher-rung task
        - The task is NOT able to be solved (given the library and config).
        - The search DOES run to exhaustion.
        - Generally, these search costs are higher than for already-solved tasks. [?]
- Example 1:
    - Ladder height: 5 rungs (including top)
    - Demo tasks: 2 per rung, 1 for top
    - With OPTIMAL CURRICULUM:
        - Wake 1: 2 CR tasks
        - Wake 2: 2 CR tasks
        - Wake 3: 2 CR tasks
        - Wake 4: 2 CR tasks
        - Wake 5: 1 CR task (top)
        - Total: 9 CR tasks
    - With FULL CURRICULUM:
        - Wake 1: 2 CR, 7 HR
        - Wake 2: 2 CR, 2 LR, 5 HR
        - Wake 3: 2 CR, 4 LR, 3 HR
        - Wake 4: 2 CR, 6 LR, 1 HR
        - Wake 5: 1 CR, 8 LR
        - Total:
            - 9 CR
            - 16 HR
            - 20 LR
- Doing the general math:
    - For the core equation:
    - Variables:
        - H = ladder height
        - R = bridging rung count
        - T_r = demo task count per bridging rung
        - T_t = top task count
    - Totals:
        - CR = T_r * (H-1) + T_t
            - = R * T_r + T_t
        - LR =

I’m trying to figure out the math for LR count and HR count. I think it might require sums, right?

---

### **ChatGPT**

Yes—**LR and HR require finite sums**, because the number of lower- and higher-rung tasks changes at each wake.

Let:

- $R$ = number of bridging rungs
- $H=R+1$ = total ladder height, including the top rung
- $T_r$ = demo tasks per bridging rung
- $T_t$ = top-rung tasks
- $N=RT_r+T_t$ = total tasks in the ladder

Assume:

1. There is one wake per rung.
2. In the full curriculum, every task is run during every wake.
3. A task belongs to exactly one rung.
4. During its own rung’s wake, it is classified as current-rung.
5. Before that wake, it is higher-rung; after that wake, it is lower-rung.

## Per-wake counts

Index the bridging-rung wakes by

$$w\in\{1,\dots,R\}$$

and let $w=R+1$ be the top-rung wake.

For a bridging-rung wake $w$:

$$\boxed{\operatorname{CR}_w=T_r}$$

$$\boxed{\operatorname{LR}_w=(w-1)T_r}$$

$$\boxed{\operatorname{HR}_w=(R-w)T_r+T_t}$$

For the top-rung wake:

$$\boxed{\operatorname{CR}_{R+1}=T_t}$$

$$\boxed{\operatorname{LR}_{R+1}=RT_r}$$

$$\boxed{\operatorname{HR}_{R+1}=0}$$

As a sanity check, every wake runs all $N$ tasks:

$$\operatorname{LR}_w+\operatorname{CR}_w+\operatorname{HR}_w=N$$

# Total current-rung runs

You already have this:

$$\boxed{\operatorname{CR}=RT_r+T_t}$$

Equivalently:

$$\boxed{\operatorname{CR}=(H-1)T_r+T_t}$$

Each task is current-rung exactly once.

# Total lower-rung runs

At successive wakes, the LR counts are:

$$0,\ T_r,\ 2T_r,\ \dots,\ RT_r$$

Therefore:

$$\operatorname{LR}
=
T_r\sum_{j=0}^{R}j$$

Using

$$\sum_{j=0}^{R}j=\frac{R(R+1)}{2}$$

we get:

$$\boxed{\operatorname{LR}=T_r\frac{R(R+1)}{2}}$$

Or in terms of $H$:

$$\boxed{\operatorname{LR}=T_r\frac{H(H-1)}{2}}$$

## Intuition

A task on bridging rung $j$ is rerun as a lower-rung task during every subsequent wake:

$$R+1-j$$

times. Thus another equivalent expression is:

$$\operatorname{LR}
=
T_r\sum_{j=1}^{R}(R+1-j)$$

# Total higher-rung runs

At bridging wake $w$, the higher-rung task count is:

$$(R-w)T_r+T_t$$

Therefore:

$$\operatorname{HR}
=
\sum_{w=1}^{R}\left((R-w)T_r+T_t\right)$$

Separate the terms:

$$\operatorname{HR}
=
T_r\sum_{w=1}^{R}(R-w)
+
\sum_{w=1}^{R}T_t$$

Since:

$$\sum_{w=1}^{R}(R-w)
=
0+1+\dots+(R-1)
=
\frac{R(R-1)}{2}$$

we get:

$$\boxed{
\operatorname{HR}
=
T_r\frac{R(R-1)}{2}
+
RT_t
}$$

Or in terms of $H$:

$$\boxed{
\operatorname{HR}
=
T_r\frac{(H-1)(H-2)}{2}
+
(H-1)T_t
}$$

The $RT_t$ term arises because every top task is higher-rung during all $R$ bridging-rung wakes.

# Your example

Given:

$$R=4,\qquad H=5,\qquad T_r=2,\qquad T_t=1$$

Current-rung:

$$\operatorname{CR}=4(2)+1=9$$

Lower-rung:

$$\operatorname{LR}
=
2\frac{4(5)}{2}
=
20$$

Higher-rung:

$$\operatorname{HR}
=
2\frac{4(3)}{2}+4(1)
=
12+4
=
16$$

So:

$$\boxed{\operatorname{CR}=9,\quad \operatorname{LR}=20,\quad \operatorname{HR}=16}$$

Total task-search executions:

$$9+20+16=45$$

This also follows directly from:

$$\text{tasks per wake}\times\text{wakes}
=
9\times5
=
45$$

# A useful simplification: total curriculum tax

If the **execution-count curriculum tax** is all non-current task runs, then:

$$\operatorname{Tax}_{\text{count}}
=
\operatorname{LR}+\operatorname{HR}$$

Substituting:

$$\operatorname{Tax}_{\text{count}}
=
T_r\frac{R(R+1)}{2}
+
T_r\frac{R(R-1)}{2}
+
RT_t$$

The two triangular terms simplify:

$$\frac{R(R+1)+R(R-1)}{2}=R^2$$

Therefore:

$$\boxed{
\operatorname{Tax}_{\text{count}}
=
R^2T_r+RT_t
}$$

Factorizing:

$$\boxed{
\operatorname{Tax}_{\text{count}}
=
R(RT_r+T_t)
=
R\operatorname{CR}
}$$

Since $N=RT_r+T_t$:

$$\boxed{
\operatorname{Tax}_{\text{count}}=RN
}$$

This has a clean interpretation: under the full curriculum, every task is run in all $R+1$ wakes. Exactly one run is current-rung, and the other $R$ runs are curriculum-tax runs. Therefore every task incurs exactly $R$ non-current executions.

The ratio of full-curriculum runs to optimal-curriculum runs is consequently:

$$\boxed{
\frac{\operatorname{Full}}{\operatorname{Optimal}}
=
\frac{(R+1)N}{N}
=
R+1
=
H
}$$

So purely by **number of task-search invocations**, a full curriculum costs $H$ times as much as an optimal curriculum.

## Important qualification: execution count is not search cost

The equations above count **search invocations**, not computational cost. Your conceptual distinction is important because:

$$C_{\mathrm{HR}}>C_{\mathrm{CR}}$$

may often hold when higher-rung searches exhaust the budget, while lower-rung cost can vary substantially with library growth.

A first coarse cost model would be:

$$\boxed{
C_{\mathrm{full}}
=
\operatorname{LR}\bar c_{\mathrm{LR}}
+
\operatorname{CR}\bar c_{\mathrm{CR}}
+
\operatorname{HR}\bar c_{\mathrm{HR}}
}$$

But this hides the phenomenon you care about. A better model indexes cost by task and wake:

$$\boxed{
C_{\mathrm{full}}
=
\sum_{w=1}^{R+1}
\sum_{i=1}^{N}
c(i,w,L_w,\theta_w)
}$$

where:

- $L_w$ is the library available at wake $w$,
- $\theta_w$ is the search configuration,
- $c(i,w,\cdot)$ is the actual search effort for task $i$.

Then the computational curriculum tax relative to optimal curriculum is:

$$\boxed{
C_{\mathrm{tax}}
=
C_{\mathrm{full}}-C_{\mathrm{optimal}}
}$$

That formulation captures both effects of library growth:

$$\text{larger search vocabulary}
\quad\longrightarrow\quad
\text{greater branching factor}$$

and:

$$\text{useful learned abstractions}
\quad\longrightarrow\quad
\text{shorter or easier solutions}$$

So I would distinguish explicitly between:

$$\boxed{\text{curriculum invocation tax}}$$

and:

$$\boxed{\text{curriculum compute tax}}$$

The first has the clean closed forms above; the second is an empirical or search-model-dependent weighted sum.

---

### **You**

What about equations for lower-rung tax and higher-rung tax, that takes into account computational cost?

---

### **ChatGPT**

Yes. The key is to define **tax relative to the computation that would occur under the optimal curriculum**, rather than merely multiplying invocation counts by an average cost.

Let:

- $R$ = number of bridging rungs
- $H=R+1$ = ladder height including the top
- $T_j$ = number of tasks assigned to rung $j$, for $j\in\{1,\dots,H\}$
- $T_1=\cdots=T_R=T_r$, and $T_H=T_t$, in your uniform setup
- $L_w$ = library available during wake $w$
- $\theta_w$ = search configuration during wake $w$
- $c_{i,j}(w)$ = computational cost of running task $i$ from rung $j$ during wake $w$

A task from rung $j$ is:

$$\begin{cases}
\text{higher-rung} & w<j\\
\text{current-rung} & w=j\\
\text{lower-rung} & w>j
\end{cases}$$

## Gross lower-rung compute tax

The total computation spent rerunning previously solved tasks is:

$$\boxed{
C_{\mathrm{LR}}
=
\sum_{j=1}^{H}
\sum_{i=1}^{T_j}
\sum_{w=j+1}^{H}
c_{i,j}(w)
}$$

This is the most general lower-rung tax equation.

It sums, for every task:

- all wakes after its intended rung;
- the actual search cost under the library and configuration present at that later wake.

For the uniform ladder:

$$\boxed{
C_{\mathrm{LR}}
=
\sum_{j=1}^{R}
\sum_{i=1}^{T_r}
\sum_{w=j+1}^{H}
c_{i,j}(w)
}$$

The top rung contributes no lower-rung runs because there are no later wakes.

## Gross higher-rung compute tax

The total computation spent attempting tasks before they are intended to be solvable is:

$$\boxed{
C_{\mathrm{HR}}
=
\sum_{j=1}^{H}
\sum_{i=1}^{T_j}
\sum_{w=1}^{j-1}
c_{i,j}(w)
}$$

For the uniform ladder:

$$\boxed{
C_{\mathrm{HR}}
=
\sum_{j=1}^{R}
\sum_{i=1}^{T_r}
\sum_{w=1}^{j-1}
c_{i,j}(w)
+
\sum_{i=1}^{T_t}
\sum_{w=1}^{R}
c_{i,H}(w)
}$$

The second term is the cost of trying top-rung tasks during every earlier wake.

## Total computational curriculum tax

Under your definition, all non-current-rung work is tax:

$$\boxed{
C_{\mathrm{tax}}
=
C_{\mathrm{LR}}+C_{\mathrm{HR}}
}$$

Equivalently:

$$\boxed{
C_{\mathrm{tax}}
=
\sum_{j=1}^{H}
\sum_{i=1}^{T_j}
\sum_{\substack{w=1\\w\neq j}}^{H}
c_{i,j}(w)
}$$

That is the cleanest general equation.

## Current-rung, optimal-curriculum cost

The optimal curriculum runs each task only at its intended wake:

$$\boxed{
C_{\mathrm{optimal}}
=
C_{\mathrm{CR}}
=
\sum_{j=1}^{H}
\sum_{i=1}^{T_j}
c_{i,j}(j)
}$$

The full-curriculum cost is:

$$\boxed{
C_{\mathrm{full}}
=
C_{\mathrm{optimal}}
+
C_{\mathrm{LR}}
+
C_{\mathrm{HR}}
}$$

Therefore:

$$\boxed{
C_{\mathrm{tax}}
=
C_{\mathrm{full}}-C_{\mathrm{optimal}}
}$$

This is useful because it gives you a direct empirical procedure: measure full-curriculum compute and subtract optimal-curriculum compute.

# Average-cost approximations

If you do not want task-level cost notation, you can use average costs.

Let:

- $\bar c_{\mathrm{LR}}$ = average cost of a lower-rung run
- $\bar c_{\mathrm{HR}}$ = average cost of a higher-rung run
- $\bar c_{\mathrm{CR}}$ = average cost of a current-rung run

Then:

$$\boxed{
C_{\mathrm{LR}}
\approx
N_{\mathrm{LR}}\bar c_{\mathrm{LR}}
}$$

$$\boxed{
C_{\mathrm{HR}}
\approx
N_{\mathrm{HR}}\bar c_{\mathrm{HR}}
}$$

Using the invocation counts derived earlier:

$$N_{\mathrm{LR}}
=
T_r\frac{R(R+1)}{2}$$

and:

$$N_{\mathrm{HR}}
=
T_r\frac{R(R-1)}{2}
+
RT_t$$

so:

$$\boxed{
C_{\mathrm{LR}}
\approx
T_r\frac{R(R+1)}{2}\bar c_{\mathrm{LR}}
}$$

$$\boxed{
C_{\mathrm{HR}}
\approx
\left(
T_r\frac{R(R-1)}{2}
+
RT_t
\right)
\bar c_{\mathrm{HR}}
}$$

And:

$$\boxed{
C_{\mathrm{tax}}
\approx
T_r\frac{R(R+1)}{2}\bar c_{\mathrm{LR}}
+
\left(
T_r\frac{R(R-1)}{2}
+
RT_t
\right)\bar c_{\mathrm{HR}}
}$$

This is probably the simplest usable closed-form model.

But it assumes all LR runs have approximately the same cost and all HR runs have approximately the same cost. For library learning, that may be too coarse.

# Wake-specific cost model

A better approximation lets average cost vary by wake:

- $\bar c_{\mathrm{LR},w}$ = average lower-rung task cost at wake $w$
- $\bar c_{\mathrm{HR},w}$ = average higher-rung task cost at wake $w$

At bridging wake $w\in\{1,\dots,R\}$:

$$N_{\mathrm{LR},w}=(w-1)T_r$$

$$N_{\mathrm{HR},w}=(R-w)T_r+T_t$$

At the top wake $H=R+1$:

$$N_{\mathrm{LR},H}=RT_r,
\qquad
N_{\mathrm{HR},H}=0$$

Therefore:

$$\boxed{
C_{\mathrm{LR}}
\approx
\sum_{w=1}^{R}
(w-1)T_r\,\bar c_{\mathrm{LR},w}
+
RT_r\,\bar c_{\mathrm{LR},H}
}$$

or more compactly:

$$\boxed{
C_{\mathrm{LR}}
\approx
\sum_{w=1}^{H}
N_{\mathrm{LR},w}\bar c_{\mathrm{LR},w}
}$$

And:

$$\boxed{
C_{\mathrm{HR}}
\approx
\sum_{w=1}^{R}
\left((R-w)T_r+T_t\right)\bar c_{\mathrm{HR},w}
}$$

This model captures the fact that the library changes over wakes.

For example:

- LR search cost may increase because the primitive pool is larger.
- LR search cost may decrease because useful abstractions produce shorter solutions.
- HR cost may increase as the search space grows.
- HR cost may remain fixed if every failed search simply consumes a fixed budget.

# If higher-rung searches run to exhaustion

Suppose every higher-rung task receives a fixed exhaustive search budget $B_w$ at wake $w$.

Then:

$$\bar c_{\mathrm{HR},w}=B_w$$

and therefore:

$$\boxed{
C_{\mathrm{HR}}
=
\sum_{w=1}^{R}
\left((R-w)T_r+T_t\right)B_w
}$$

If the budget is constant across wakes, $B_w=B$, then:

$$\boxed{
C_{\mathrm{HR}}
=
B\left(
T_r\frac{R(R-1)}{2}
+
RT_t
\right)
}$$

This is a strong model when:

- higher-rung tasks are genuinely unsolvable at those wakes;
- exhaustive failure consumes the full budget;
- the budget is the relevant compute unit.

If the search budget expands with library size, you would instead use something such as:

$$B_w=B(L_w,\theta_w)$$

and retain the wake-specific sum.

# A more explicit lower-rung search model

For LR tasks, cost is likely determined by at least three factors:

1. Search-space breadth from library growth.
2. Depth or description length of the discovered solution.
3. Early-stopping behaviour.

You could model lower-rung task cost as:

$$\boxed{
c_{i,j}^{\mathrm{LR}}(w)
=
g\left(
|L_w|,
d_{i,j}(L_w),
p_{i,j}(L_w),
\theta_w
\right)
}$$

where:

- $|L_w|$ = number of available primitives or abstractions;
- $d_{i,j}(L_w)$ = depth or size of the shortest available solution;
- $p_{i,j}(L_w)$ = search priority or probability assigned to that solution;
- $\theta_w$ = enumerator, beam width, timeout, early-stopping rule, etc.

Then:

$$\boxed{
C_{\mathrm{LR}}
=
\sum_{j=1}^{R}
\sum_{i=1}^{T_r}
\sum_{w=j+1}^{H}
g\left(
|L_w|,
d_{i,j}(L_w),
p_{i,j}(L_w),
\theta_w
\right)
}$$

For enumerative search, a rough stylized cost model might be:

$$c_{i,j}^{\mathrm{LR}}(w)
\propto
b_w^{d_{i,j}(w)}$$

where $b_w$ is an effective branching factor.

Thus:

$$\boxed{
C_{\mathrm{LR}}
\propto
\sum_{j=1}^{R}
\sum_{i=1}^{T_r}
\sum_{w=j+1}^{H}
b_w^{d_{i,j}(w)}
}$$

This makes the competing effects explicit:

- library growth tends to increase $b_w$;
- useful learned abstractions tend to reduce $d_{i,j}(w)$.

The net LR cost can therefore rise or fall.

# Gross tax versus marginal tax

There is an important conceptual distinction.

The equations above define **gross curriculum tax**: all work on non-current tasks.

But sometimes you may want to ask whether rerunning a lower-rung task has some value—for example:

- validating that an abstraction remains usable;
- collecting reuse statistics;
- enabling abstraction revision;
- detecting regressions;
- generating evidence for library compression.

If that work has value, calling all of it “tax” may overstate the waste.

You could define:

$$\boxed{
C_{\mathrm{LR,tax}}^{\mathrm{net}}
=
C_{\mathrm{LR}}-V_{\mathrm{LR}}
}$$

where $V_{\mathrm{LR}}$ is the compute-equivalent value of the information or learning produced by those reruns.

Likewise:

$$\boxed{
C_{\mathrm{HR,tax}}^{\mathrm{net}}
=
C_{\mathrm{HR}}-V_{\mathrm{HR}}
}$$

For example, failed higher-rung attempts could still provide:

- partial programs;
- search traces;
- negative evidence;
- pressure to invent abstractions;
- training data for search control.

For straightforward benchmarking, though, I would first report gross compute tax and treat any learning benefit separately.

# Useful normalized metrics

Raw compute tax is useful, but normalization makes ladders comparable.

## Lower-rung tax ratio

$$\boxed{
\tau_{\mathrm{LR}}
=
\frac{C_{\mathrm{LR}}}{C_{\mathrm{optimal}}}
}$$

## Higher-rung tax ratio

$$\boxed{
\tau_{\mathrm{HR}}
=
\frac{C_{\mathrm{HR}}}{C_{\mathrm{optimal}}}
}$$

## Total curriculum tax ratio

$$\boxed{
\tau_{\mathrm{total}}
=
\frac{C_{\mathrm{LR}}+C_{\mathrm{HR}}}
{C_{\mathrm{optimal}}}
}$$

## Full-curriculum compute multiplier

$$\boxed{
M_{\mathrm{full}}
=
\frac{C_{\mathrm{full}}}{C_{\mathrm{optimal}}}
=
1+\tau_{\mathrm{LR}}+\tau_{\mathrm{HR}}
}$$

This is the compute analogue of the earlier invocation-count multiplier $H$. Unlike the count multiplier, it need not equal $H$, because LR, CR, and HR runs can have very different costs.

# Your example under a simple cost model

For:

$$R=4,\qquad T_r=2,\qquad T_t=1$$

you had:

$$N_{\mathrm{LR}}=20,\qquad
N_{\mathrm{HR}}=16,\qquad
N_{\mathrm{CR}}=9$$

Suppose average costs are:

$$\bar c_{\mathrm{LR}}=30$$

$$\bar c_{\mathrm{CR}}=100$$

cˉCR​=100

$$\bar c_{\mathrm{HR}}=250$$

in arbitrary compute units.

Then:

$$C_{\mathrm{LR}}=20(30)=600$$

$$C_{\mathrm{HR}}=16(250)=4000$$

CHR​=16(250)=4000

$$C_{\mathrm{optimal}}=9(100)=900$$

So:

$$C_{\mathrm{tax}}=600+4000=4600$$

and:

$$C_{\mathrm{full}}=900+4600=5500$$

The tax ratios are:

$$\tau_{\mathrm{LR}}=\frac{600}{900}=0.667$$

$$\tau_{\mathrm{HR}}=\frac{4000}{900}=4.444$$

$$\tau_{\mathrm{total}}=\frac{4600}{900}=5.111$$

and the full-curriculum compute multiplier is:

$$M_{\mathrm{full}}
=
\frac{5500}{900}
\approx6.11$$

Even though the invocation-count multiplier is only:

$$H=5$$

the compute multiplier is larger because failed HR searches are much more expensive.

## Recommended canonical definitions

I would formalize the quantities as:

$$\boxed{
\mathrm{LR\ Tax}
=
\sum_{j=1}^{H}
\sum_{i=1}^{T_j}
\sum_{w=j+1}^{H}
c_{i,j}(w)
}$$

$$\boxed{
\mathrm{HR\ Tax}
=
\sum_{j=1}^{H}
\sum_{i=1}^{T_j}
\sum_{w=1}^{j-1}
c_{i,j}(w)
}$$

$$\boxed{
\mathrm{Curriculum\ Tax}
=
\mathrm{LR\ Tax}+\mathrm{HR\ Tax}
}$$

and, for reporting across experiments:

$$\boxed{
\mathrm{Normalized\ Curriculum\ Tax}
=
\frac{\mathrm{LR\ Tax}+\mathrm{HR\ Tax}}
{\mathrm{Current\text{-}Rung\ Compute}}
}$$

The main empirical question then becomes how to define $c_{i,j}(w)$. The best answer is probably not wall-clock time alone, but a hardware-independent search-effort measure such as:

- programs enumerated;
- nodes expanded;
- candidate evaluations;
- model forward-pass FLOPs;
- interpreter execution steps;
- or actual estimated FLOPs.

Wall-clock time can then be reported as a secondary operational metric.

---

### **You**

- Q: Overall, what are the best things to try to empirically measure here?
    - And especially, what can be normalized?
    - Q: Are there certain constants or variables that we can predict to be consistent across ladders with different properties?

---

### **ChatGPT**

The central methodological point is: **do not collapse “computational cost” into one number too early**. Program-library learning changes both the *surface search space* and the *amount of computation hidden inside each library call*. DreamCoder-style work often reports tasks solved and time-to-solution, with component ablations; subsequent work explicitly describes neural guidance as reducing search breadth and library abstractions as reducing search depth, while library-learning systems also use corpus compressivity as a quality measure. [\[Image\]DOI+2\[Image\]Proceedings of Machine Learning Research+2](https://doi.org/10.1098/rsta.2022.0050?urlappend=%3Futm_source%3Dresearchgate.net%26utm_medium%3Darticle&utm_source=chatgpt.com)

I would build the measurement framework around **task-run records**, then derive several normalized views.

# 1. The fundamental observational unit

Let a task be:

$$q=(j,k)$$

where:

- $j\in\{1,\ldots,H\}$ is its intended rung;
- $k\in\{1,\ldots,T_j\}$ identifies the task within that rung.

Let:

$$c^{(m)}_{q,w}$$

be the cost of searching task $q$ during wake $w$, measured using resource metric $m$.

Each task-run should record at least:

| Category | Measurements |
| --- | --- |
| Search generation | candidates generated, search nodes expanded, grammar productions applied |
| Semantic evaluation | candidates evaluated, examples executed, primitive interpreter operations |
| Neural guidance | forward passes, tokens, FLOPs or approximate FLOPs |
| Outcome | solved, exhausted, timeout, solution rank |
| Solution | AST size, expanded AST size, description length, abstractions used |
| Operational | CPU time, wall time, peak memory |
| Context | wake, intended rung, library snapshot, search-policy snapshot, seed, budget |

Then all LR and HR equations can be applied **component-wise**:

$$C_{\mathrm{LR}}^{(m)}
=
\sum_{j=1}^{H}
\sum_{k=1}^{T_j}
\sum_{w=j+1}^{H}
c^{(m)}_{(j,k),w}$$

$$C_{\mathrm{HR}}^{(m)}
=
\sum_{j=1}^{H}
\sum_{k=1}^{T_j}
\sum_{w=1}^{j-1}
c^{(m)}_{(j,k),w}$$

This gives you, for example:

$$C_{\mathrm{LR}}^{(\text{candidates})},
\quad
C_{\mathrm{LR}}^{(\text{primitive ops})},
\quad
C_{\mathrm{LR}}^{(\text{FLOPs})},
\quad
C_{\mathrm{LR}}^{(\text{CPU seconds})}$$

rather than one potentially misleading number.

## The two most important compute measures

For your system, I would prioritize:

### Surface search work

$$c^{(\mathrm{surface})}_{q,w}
=
\text{number of candidate programs semantically evaluated}$$

This measures how difficult the search appears in the learned DSL.

### Expanded semantic work

$$c^{(\mathrm{expanded})}_{q,w}
=
\sum_{p\text{ evaluated}}
\text{primitive-level operations required to execute }p$$

This recursively expands learned abstractions into their underlying operations.

The distinction matters. Suppose an abstraction collapses a 30-node expression into one library call. Candidate count and surface AST size may fall dramatically, even though executing that abstraction still performs substantial work. You want to measure both the **search advantage** and the **actual interpreter computation**.

Wall-clock time should be secondary because it is affected by hardware, implementation, caching, parallelism and runtime noise.

# 2. Core normalized tax metrics

## A. Cost per tax exposure

The simplest normalization removes ladder geometry.

For arbitrary per-rung task counts:

$$N_{\mathrm{LR}}
=
\sum_{j=1}^{H}T_j(H-j)$$

$$N_{\mathrm{HR}}
=
\sum_{j=1}^{H}T_j(j-1)$$

Then:

$$\boxed{
\mu_{\mathrm{LR}}^{(m)}
=
\frac{C_{\mathrm{LR}}^{(m)}}{N_{\mathrm{LR}}}
}$$

$$\boxed{
\mu_{\mathrm{HR}}^{(m)}
=
\frac{C_{\mathrm{HR}}^{(m)}}{N_{\mathrm{HR}}}
}$$

These answer:

> How expensive is the average unnecessary lower-rung or higher-rung search invocation?

This is probably your primary cross-ladder normalization.

Report both the arithmetic mean and median. The arithmetic mean correctly represents total compute, while the median or geometric mean better characterizes a heavy-tailed task distribution.

## B. Tax relative to useful current-rung compute

Define:

$$C_{\mathrm{CR}}^{(m)}
=
\sum_{j=1}^{H}
\sum_{k=1}^{T_j}
c^{(m)}_{(j,k),j}$$

Then:

$$\boxed{
\tau_{\mathrm{LR}}^{(m)}
=
\frac{C_{\mathrm{LR}}^{(m)}}{C_{\mathrm{CR}}^{(m)}}
}$$

$$\boxed{
\tau_{\mathrm{HR}}^{(m)}
=
\frac{C_{\mathrm{HR}}^{(m)}}{C_{\mathrm{CR}}^{(m)}}
}$$

$$\boxed{
\tau_{\mathrm{total}}^{(m)}
=
\tau_{\mathrm{LR}}^{(m)}
+
\tau_{\mathrm{HR}}^{(m)}
}$$

And:

$$\boxed{
M_{\mathrm{full}}^{(m)}
=
\frac{C_{\mathrm{full}}^{(m)}}{C_{\mathrm{CR}}^{(m)}}
=
1+\tau_{\mathrm{LR}}^{(m)}+\tau_{\mathrm{HR}}^{(m)}
}$$

This answers:

> How many units of curriculum overhead are paid for each unit of useful acquisition compute?

It is especially intuitive for communicating the curriculum tax.

## C. Tax as a share of full computation

$$\boxed{
s_{\mathrm{LR}}^{(m)}
=
\frac{C_{\mathrm{LR}}^{(m)}}{C_{\mathrm{full}}^{(m)}}
}$$

$$\boxed{
s_{\mathrm{HR}}^{(m)}
=
\frac{C_{\mathrm{HR}}^{(m)}}{C_{\mathrm{full}}^{(m)}}
}$$

This produces a decomposition such as:

$$18\%\text{ CR},\qquad
12\%\text{ LR tax},\qquad
70\%\text{ HR tax}$$

It is descriptively useful, although the ratios against $C_{\mathrm{CR}}$ are generally more analytically useful.

# 3. Normalize by rung distance

A task that is one rung premature is categorically different from one attempted four rungs too early.

Define the signed rung distance:

$$d=w-j$$

Thus:

- $d<0$: higher-rung;
- $d=0$: current-rung;
- $d>0$: lower-rung.

For LR distance $d>0$:

$$N_{\mathrm{LR}}(d)
=
\sum_{j=1}^{H-d}T_j$$

$$\boxed{
\mu_{\mathrm{LR}}^{(m)}(d)
=
\frac{
\displaystyle
\sum_{j=1}^{H-d}
\sum_{k=1}^{T_j}
c^{(m)}_{(j,k),j+d}
}{
N_{\mathrm{LR}}(d)
}
}$$

μLR(m)​(d)=NLR​(d)j=1∑H−d​k=1∑Tj​​c(j,k),j+d(m)​​​

For HR distance $d>0$:

$$N_{\mathrm{HR}}(d)
=
\sum_{j=d+1}^{H}T_j$$

$$\boxed{
\mu_{\mathrm{HR}}^{(m)}(d)
=
\frac{
\displaystyle
\sum_{j=d+1}^{H}
\sum_{k=1}^{T_j}
c^{(m)}_{(j,k),j-d}
}{
N_{\mathrm{HR}}(d)
}
}$$

This gives you a **tax-distance curve**.

For your uniform bridging-rung setup:

$$N_{\mathrm{LR}}(d)
=
(R+1-d)T_r$$

$$N_{\mathrm{HR}}(d)
=
(R-d)T_r+T_t$$

for $d\in\{1,\ldots,R\}$.

This normalization is one of the best ways to compare ladders with different heights. Rather than comparing aggregate HR tax on a height-4 ladder against aggregate HR tax on a height-10 ladder, compare:

$$\mu_{\mathrm{HR}}(1),\quad
\mu_{\mathrm{HR}}(2),\quad\ldots$$

The curve can reveal whether “prematurity distance” predicts search cost.

# 4. Normalize against the search budget

Let $B^{(m)}_{q,w}$ be the applicable search budget.

Define utilization:

$$\boxed{
u^{(m)}_{q,w}
=
\frac{c^{(m)}_{q,w}}{B^{(m)}_{q,w}}
}$$

with:

$$0\leq u^{(m)}_{q,w}\leq1$$

Then report:

$$\bar u_{\mathrm{LR}},
\qquad
\bar u_{\mathrm{CR}},
\qquad
\bar u_{\mathrm{HR}}$$

If every HR task is genuinely unsolvable and search always exhausts its budget:

$$\boxed{
u_{\mathrm{HR}}=1
}$$

That becomes a highly predictable conditional invariant.

For LR tasks, utilization measures early-stopping effectiveness:

$$u_{\mathrm{LR}}\ll1$$

means previously solved tasks are being recovered cheaply.

This metric normalizes across wakes with different absolute budgets, but it does **not** normalize differences in the quality of those budgets. A budget of one million candidate evaluations in one DSL may represent a radically different search frontier from the same count in another DSL.

# 5. Normalize each task against its current-rung cost

For a task $q=(j,k)$, its current-rung cost is:

$$c^{(m)}_{q,j}$$

Define the task-relative cost:

$$\boxed{
\rho^{(m)}_{q,w}
=
\frac{c^{(m)}_{q,w}}{c^{(m)}_{q,j}}
}$$

Interpretation:

- $\rho_{\mathrm{LR}}<1$: the task is cheaper to resolve later;
- $\rho_{\mathrm{LR}}>1$: library growth has made it more expensive;
- $\rho_{\mathrm{HR}}>1$: premature exhaustive search costs more than eventual successful search;
- $\rho_{\mathrm{HR}}<1$: possible when the failed early budget is small.

Because ratios may be highly skewed, I would aggregate:

$$\boxed{
\ell^{(m)}_{q,w}
=
\log
\frac{c^{(m)}_{q,w}+\epsilon}
{c^{(m)}_{q,j}+\epsilon}
}$$

The mean of $\ell$ corresponds to a geometric-mean cost ratio.

This is a strong normalization because each task acts as its own control. Its limitation is that the denominator is affected by the library and search policy available at wake $j$, so it does not isolate every causal mechanism.

# 6. Directly measure search-space difficulty

Raw library size is not a good enough normalization. Two libraries with 20 components can have very different:

- type distributions;
- arities;
- grammar probabilities;
- compositional branching;
- redundancies;
- useful abstractions.

Better metrics are solution rank and solution surprisal.

## Solution rank

Let:

$$r_{q,w}
=
\text{number of candidates considered before finding a solution}$$

Then:

$$\boxed{
D^{(\mathrm{rank})}_{q,w}
=
\log_2(r_{q,w}+1)
}$$

This can be interpreted loosely as search-difficulty bits.

For unsolved searches:

$$r_{q,w}>B_{q,w}$$

is right-censored rather than observed exactly. Do not record it as equal to the budget; record that it exceeded the budget.

## Solution surprisal

If your search grammar or recognition model gives a probability to programs:

$$\boxed{
D^{(\mathrm{prior})}_{q,w}
=
-\log_2 P(p^*_{q,w}\mid x_q,L_w,\theta_w)
}$$

where $p^*_{q,w}$ is the best available solution under the relevant criterion.

This is particularly useful because it captures both:

- library-induced shortening of the solution;
- search-policy probability assigned to it.

However, it remains a model-based proxy, not actual search cost. Two search procedures can turn the same program probability into different enumeration costs.

# 7. Measure the two opposing effects on LR tasks

You correctly identified that later library growth can both help and hurt lower-rung tasks.

For a task solved at rung $j$, compare its replay at wake $w>j$ under:

- the original snapshot $L_j$;
- the later snapshot $L_w$.

Define:

$$\boxed{
\Delta^{(m)}_{\mathrm{library}}(q,w)
=
c^{(m)}(q;L_w,\theta_w)
-
c^{(m)}(q;L_j,\theta_j)
}$$

Then:

$$\Delta_{\mathrm{library}}>0$$

means the evolved system makes the old task harder, while:

$$\Delta_{\mathrm{library}}<0$$

means later learning makes it easier.

But this combines at least two forces:

$$\Delta_{\mathrm{library}}
=
\text{vocabulary-dilution penalty}
+
\text{abstraction benefit}
+
\text{search-policy change}
+
\text{interactions}$$

A useful diagnostic is to preserve the original solution $p^{\mathrm{old}}_q$.

Measure its later surprisal:

$$D_{\mathrm{old}}(q,w)
=
-\log_2P(p^{\mathrm{old}}_q\mid x_q,L_w,\theta_w)$$

Then measure the best later solution:

$$D_{\mathrm{best}}(q,w)
=
\min_{p\models q}
-\log_2P(p\mid x_q,L_w,\theta_w)$$

The difference:

$$\boxed{
G_{\mathrm{new\ abstraction}}(q,w)
=
D_{\mathrm{old}}(q,w)-D_{\mathrm{best}}(q,w)
}$$

measures how much a newer solution compensates for—or exceeds—the dilution of the old one.

A positive value means the later library offers a substantially easier route than replaying the original program.

# 8. Outcome-adjusted measurements

Compute tax alone does not tell you whether running the full curriculum was worthwhile.

## Compute-to-acquisition

For each rung $j$, measure cumulative compute before its tasks become solvable:

$$\boxed{
C_{\rightarrow j}^{(m)}
=
\sum_{w=1}^{j}
C_w^{(m)}
}$$

For the top rung:

$$\boxed{
C_{\rightarrow\mathrm{top}}^{(m)}
}$$

This may be the single most practically relevant end-to-end metric:

> How much computation did the system require to acquire enough abstractions to solve the top task?

## Success-versus-budget curve

Let:

$$S(K)
=
\frac{\text{tasks solved within compute budget }K}
{\text{tasks attempted}}$$

Plot $S(K)$ against a hardware-independent search measure such as candidates evaluated or primitive operations.

You can normalize its area:

$$\boxed{
\operatorname{AUC}_{\log K}
=
\frac{
\displaystyle
\int_{\log K_{\min}}^{\log K_{\max}}
S(K)\,d\log K
}{
\log K_{\max}-\log K_{\min}
}
}$$

This lies between 0 and 1 and rewards methods that solve tasks earlier across multiple budgets, rather than only reporting performance at one timeout.

## Retention

For LR tasks:

$$\boxed{
\operatorname{Retention}(w)
=
\frac{
\text{previously solved tasks still solved within a fixed budget at }w
}{
\text{tasks solved before }w
}
}$$

This distinguishes:

- “still technically solvable with unlimited search”;
- “still accessible at a reasonable search cost.”

That is especially relevant to library bloat and interference.

# 9. Library-level measurements

You should measure the evolving library itself, but these are explanatory variables rather than direct tax measures.

## Library size

$$|L_w|$$

Break this down by:

- primitive versus learned;
- active versus inactive;
- type and arity;
- abstraction depth.

## Corpus MDL

$$\boxed{
\operatorname{MDL}_w
=
DL(L_w)
+
\sum_{q\in Q_{\mathrm{solved}}}
DL(p_q\mid L_w)
}$$

Then normalize:

$$\boxed{
\kappa_w
=
\frac{\operatorname{MDL}_0}{\operatorname{MDL}_w}
}$$

or:

$$\boxed{
\Delta\operatorname{MDL}_w
=
\operatorname{MDL}_0-\operatorname{MDL}_w
}$$

Library-learning work uses compressivity because a useful abstraction should reduce the description length of a corpus, but compression should not be treated as interchangeable with search compute. A highly compressive abstraction can still receive low search probability or introduce substantial branching elsewhere. [\[Image\]arXiv+1](https://arxiv.org/abs/2211.16605?utm_source=chatgpt.com)

## Abstraction reuse

For abstraction $a$:

$$\operatorname{reuse}(a)
=
\left|
\{q:a\in p_q\}
\right|$$

Also measure weighted reuse:

$$\operatorname{weightedReuse}(a)
=
\sum_q n(a,p_q)$$

and marginal search utility:

$$\boxed{
U^{(m)}(a)
=
\sum_q
\left[
c^{(m)}(q;L\setminus\{a\})
-
c^{(m)}(q;L)
\right]
}$$

An abstraction-level compute return can then be:

$$\boxed{
\operatorname{ROI}(a)
=
\frac{U(a)}
{DL(a)+C_{\mathrm{learn}}(a)}
}$$

This would be a particularly interesting library-governance metric.

# 10. What is actually constant across ladders?

There are three categories.

## Exact structural invariants

These follow from the curriculum design and do not depend on task difficulty.

Let:

$$N=\sum_{j=1}^{H}T_j$$

Under a full curriculum:

$$\boxed{
N_{\mathrm{full}}=HN
}$$

Each task is current-rung exactly once:

$$\boxed{
N_{\mathrm{CR}}=N
}$$

Each task is non-current during the other $H-1=R$ wakes:

$$\boxed{
N_{\mathrm{LR}}+N_{\mathrm{HR}}=RN
}$$

Thus every task incurs exactly:

$$\boxed{R}$$

tax invocations, regardless of its intended rung.

For your uniform setup:

$$N_{\mathrm{LR}}
=
T_r\frac{R(R+1)}{2}$$

$$N_{\mathrm{HR}}
=
T_r\frac{R(R-1)}{2}+RT_t$$

NHR​=Tr​2R(R−1)​+RTt​

and:

$$\boxed{
N_{\mathrm{LR}}-N_{\mathrm{HR}}
=
R(T_r-T_t)
}$$

Therefore, when:

$$T_t=T_r$$

you get exact symmetry:

$$\boxed{
N_{\mathrm{LR}}=N_{\mathrm{HR}}
}$$

With fixed $T_r$ and $T_t$, total tax invocation count grows quadratically with ladder height:

$$RN
=
R(RT_r+T_t)
=
O(R^2)$$

That quadratic scaling is structural, not empirical.

## Conditional computational invariants

These hold only under controlled assumptions.

### Fixed exhaustive HR budget

If all HR tasks are unsolvable and every failed search consumes a constant budget $B$:

$$\boxed{
C_{\mathrm{HR}}=BN_{\mathrm{HR}}
}$$

and:

$$\boxed{
\mu_{\mathrm{HR}}=B
}$$

This is likely your strongest predictable compute relationship.

If the budget varies by wake:

$$\boxed{
C_{\mathrm{HR}}
=
\sum_{w=1}^{H-1}
N_{\mathrm{HR},w}B_w
}$$

### Controlled per-candidate execution

If all tasks have:

- the same number and size of demonstrations;
- the same interpreter;
- similar data sizes;
- primitives with controlled execution costs;

then cost per candidate may be approximately stable.

Without those controls, candidate count can remain comparable while actual computation varies substantially.

### Calibrated rung difficulty

You could deliberately design ladders so that current-rung tasks have approximately constant residual complexity:

$$DL(p^*_{q,j}\mid L_j)\approx D$$

or:

$$-\log P(p^*_{q,j}\mid x_q,L_j)\approx D$$

across rungs.

Then current-rung acquisition cost becomes more comparable across ladders. But this is a **benchmark calibration property**, not a natural consequence of being an abstraction ladder.

## Quantities that should not be assumed constant

I would not expect any of these to be invariant:

$$\mu_{\mathrm{LR}},
\quad
\mu_{\mathrm{CR}},
\quad
|L_w|,
\quad
\text{effective branching factor},
\quad
\text{solution rank},
\quad
\text{compression ratio},
\quad
\text{abstraction reuse},
\quad
\text{wall time}$$

They are precisely the quantities affected by:

- ladder structure;
- abstraction quality;
- primitive design;
- type constraints;
- search order;
- recognition policy;
- task redundancy;
- library-learning decisions.

# 11. A critical experimental distinction

There are actually two different questions hiding inside “curriculum tax.”

## Accounting tax

In a realized full-curriculum run:

$$\boxed{
C_{\mathrm{tax}}^{\mathrm{gross}}
=
C_{\mathrm{LR}}+C_{\mathrm{HR}}
}$$

This is simply how much compute was spent on non-current tasks.

## Causal marginal cost

You might instead calculate:

$$C_{\mathrm{full}}-C_{\mathrm{optimal}}$$

But this is **not necessarily pure tax**.

If LR and HR search traces affect:

- library learning;
- abstraction selection;
- recognition-model training;
- search-policy updates;
- future task solutions;

then full and optimal curricula produce different learning trajectories. Their difference contains both:

1. additional search expenditure;
2. downstream benefits or harms caused by that additional experience.

Therefore:

$$\boxed{
C_{\mathrm{full}}-C_{\mathrm{optimal}}
\neq
C_{\mathrm{LR}}+C_{\mathrm{HR}}
}$$

in the causal sense, even if it looks similar as an accounting identity under a fixed trajectory.

To isolate pure search tax, run **evaluation-only replays**:

1. Generate a reference sequence of library and policy snapshots.
2. Freeze $L_w$ and $\theta_w$ at each wake.
3. Run the CR, LR and HR task sets without allowing those evaluations to update the system.
4. Measure their costs under the identical state.

Separately, run full versus optimal curriculum as a treatment comparison to measure whether the nominally “wasted” searches produce useful learning.

A clean factorial experiment would compare:

| Condition | Tasks run during each wake |
| --- | --- |
| Optimal | CR only |
| Lower replay | CR + LR |
| Higher exploration | CR + HR |
| Full | CR + LR + HR |

Because the learned trajectories can interact, the full condition may not equal the sum of the isolated effects.

# 12. My recommended core dashboard

For every ladder, I would make these the canonical outputs:

### Structural

$$H,\quad N,\quad N_{\mathrm{CR}},\quad N_{\mathrm{LR}},\quad N_{\mathrm{HR}}$$

### Compute accounting

$$C_{\mathrm{CR}},\quad C_{\mathrm{LR}},\quad C_{\mathrm{HR}}$$

reported separately in:

- candidates evaluated;
- expanded primitive operations;
- neural FLOPs, where applicable;
- wall time as secondary.

### Normalized tax

$$\mu_{\mathrm{LR}},
\quad
\mu_{\mathrm{HR}},
\quad
\tau_{\mathrm{LR}},
\quad
\tau_{\mathrm{HR}},
\quad
M_{\mathrm{full}}$$

### Learning dynamics

$$\mu_{\mathrm{LR}}(d),
\quad
\mu_{\mathrm{HR}}(d),
\quad
\operatorname{Retention}(w),
\quad
C_{\rightarrow\mathrm{top}}$$

### Search-space diagnostics

$$\log_2(\text{solution rank}),
\quad
-\log_2P(p^*),
\quad
DL(p^*\mid L_w)$$

### Library dynamics

$$|L_w|,
\quad
\operatorname{MDL}_w,
\quad
\text{reuse distribution},
\quad
\text{marginal abstraction utility}$$

The most generally comparable headline metrics would be:

$$\boxed{
\text{mean compute per LR/HR exposure}
}$$

$$\boxed{
\text{tax compute divided by current-rung compute}
}$$

$$\boxed{
\text{compute-to-top-solution}
}$$

$$\boxed{
\text{cost as a function of signed rung distance}
}$$

Together, those separate the effect of **ladder geometry**, **search difficulty**, and **library-learning quality** rather than allowing them to collapse into one aggregate number.

**References:**

1. [DOI+2Proceedings of Machine Learning Research+2](https://doi.org/10.1098/rsta.2022.0050?urlappend=%3Futm_source%3Dresearchgate.net%26utm_medium%3Darticle&utm_source=chatgpt.com)
2. [arXiv+1](https://arxiv.org/abs/2211.16605?utm_source=chatgpt.com)

---

### **You**

Re causal marginal cost: Interesting point. Is my math here correct?

- Causal marginal cost
    - Assume we call running the ladder with learning on “learned”, and running it rung by rung with frozen reference libraries and configs “oracle”:
    - C_full_learned - C_optimal_learned is not necessarily pure tax.
        - ≠ C_tax
        - = C_tax + C_extra_learning_benefit
    - C_full_oracle - C_optimal_oracle = C_tax
    - C_extra_learning_benefit = (C_full_learned - C_optimal_learned) - (C_full_oracle - C_optimal_oracle)

---

### **ChatGPT**

Your structure is **substantially correct**, but there are two important corrections:

1. The residual term is a **signed learning-mediated cost effect**, not necessarily a benefit.
2. The oracle subtraction equals pure tax only if the full and optimal oracle runs use the **same frozen reference states**.

## 1. Recommended formulation

Let:

$$\Delta C_{\mathrm{learned}}
=
C_{\mathrm{full,learned}}
-
C_{\mathrm{optimal,learned}}$$

and:

$$\Delta C_{\mathrm{frozen}}
=
C_{\mathrm{full,frozen}}
-
C_{\mathrm{optimal,frozen}}$$

If the frozen runs use identical reference libraries and configurations at every wake, then:

$$\boxed{
C_{\mathrm{tax}}^{\mathrm{direct}}
=
\Delta C_{\mathrm{frozen}}
}$$

Define the residual:

$$\boxed{
C_{\mathrm{learning\ effect}}
=
\Delta C_{\mathrm{learned}}
-
\Delta C_{\mathrm{frozen}}
}$$

Therefore:

$$\boxed{
\Delta C_{\mathrm{learned}}
=
C_{\mathrm{tax}}^{\mathrm{direct}}
+
C_{\mathrm{learning\ effect}}
}$$

Your last equation is therefore mathematically correct if you rename:

$$C_{\mathrm{extra\ learning\ benefit}}$$

to:

$$C_{\mathrm{learning\ effect}}$$

because it can be positive or negative.

## 2. The sign of “benefit”

Suppose the direct frozen tax is:

$$\Delta C_{\mathrm{frozen}}=100$$

but additional LR and HR experience helps the full learner, so:

$$\Delta C_{\mathrm{learned}}=70$$

Then your residual is:

$$C_{\mathrm{learning\ effect}}
=
70-100=-30$$

The extra learning produced a **30-unit benefit**, but the signed residual is $-30$.

So, if you want “benefit” to be a positive-valued quantity, define:

$$\boxed{
C_{\mathrm{learning\ benefit}}
=
\Delta C_{\mathrm{frozen}}
-
\Delta C_{\mathrm{learned}}
}$$

Then:

$$\boxed{
\Delta C_{\mathrm{learned}}
=
C_{\mathrm{tax}}^{\mathrm{direct}}
-
C_{\mathrm{learning\ benefit}}
}$$

Here:

- $C_{\mathrm{learning\ benefit}}>0$: extra full-curriculum experience reduces later computation;
- $C_{\mathrm{learning\ benefit}}<0$: extra experience causes a net penalty;
- $C_{\mathrm{learning\ benefit}}=0$: it has no net effect on computation.

You could instead keep separate nonnegative quantities:

$$C_{\mathrm{benefit}}
=
\max\left(
0,
\Delta C_{\mathrm{frozen}}-\Delta C_{\mathrm{learned}}
\right)$$

$$C_{\mathrm{penalty}}
=
\max\left(
0,
\Delta C_{\mathrm{learned}}-\Delta C_{\mathrm{frozen}}
\right)$$

although the signed effect is usually more analytically convenient.

# 3. Why the learned difference is not pure tax

Let:

- $C_{\mathrm{CR,F}}$ = current-rung cost under the full learner’s trajectory;
- $C_{\mathrm{tax,F}}$ = actual LR and HR cost under the full learner’s trajectory;
- $C_{\mathrm{CR,O}}$ = current-rung cost under the optimal learner’s trajectory.

Then:

$$C_{\mathrm{full,learned}}
=
C_{\mathrm{CR,F}}
+
C_{\mathrm{tax,F}}$$

whereas:

$$C_{\mathrm{optimal,learned}}
=
C_{\mathrm{CR,O}}$$

Therefore:

$$\boxed{
\Delta C_{\mathrm{learned}}
=
C_{\mathrm{tax,F}}
+
\left(
C_{\mathrm{CR,F}}-C_{\mathrm{CR,O}}
\right)
}$$

This shows the basic confound directly.

The full-curriculum run pays LR and HR costs, but those runs can alter the learned state. Consequently, they can make later current-rung searches:

- cheaper, through useful extra learning;
- more expensive, through library bloat or misleading abstractions;
- differently successful.

Furthermore, learning can alter the cost of later LR and HR runs themselves. So the effect is not limited to current-rung computation.

# 4. The frozen-reference equation

Let the frozen reference state at wake $w$ be:

$$S_w^{\mathrm{ref}}
=
\left(
L_w^{\mathrm{ref}},
\theta_w^{\mathrm{ref}}
\right)$$

where $L_w^{\mathrm{ref}}$ is the library and $\theta_w^{\mathrm{ref}}$ is the search configuration.

Then:

$$C_{\mathrm{optimal,frozen}}
=
\sum_w
\sum_{q\in Q_w^{\mathrm{CR}}}
c(q,w;S_w^{\mathrm{ref}})$$

and:

$$C_{\mathrm{full,frozen}}
=
\sum_w
\left[
\sum_{q\in Q_w^{\mathrm{CR}}}
c(q,w;S_w^{\mathrm{ref}})
+
\sum_{q\in Q_w^{\mathrm{LR}}}
c(q,w;S_w^{\mathrm{ref}})
+
\sum_{q\in Q_w^{\mathrm{HR}}}
c(q,w;S_w^{\mathrm{ref}})
\right]$$

Subtracting gives:

$$\boxed{
C_{\mathrm{full,frozen}}
-
C_{\mathrm{optimal,frozen}}
=
\sum_w
\left[
\sum_{q\in Q_w^{\mathrm{LR}}}
c(q,w;S_w^{\mathrm{ref}})
+
\sum_{q\in Q_w^{\mathrm{HR}}}
c(q,w;S_w^{\mathrm{ref}})
\right]
}$$

That is exactly the direct LR-plus-HR execution tax **under that reference trajectory**.

# 5. The reference trajectory matters

There is not necessarily one uniquely correct frozen tax. You must decide where the frozen states come from.

Possible choices include:

### Optimal-path reference

Use libraries and configurations produced by the optimal curriculum:

$$S_w^{\mathrm{ref}}=S_w^{\mathrm{optimal}}$$

This measures:

> What would it cost to add all LR and HR task runs to the optimal learner’s state trajectory, without letting those extra runs affect learning?

This is probably the cleanest definition of the **marginal curriculum tax**.

### Full-path reference

Use the states produced by the full curriculum:

$$S_w^{\mathrm{ref}}=S_w^{\mathrm{full}}$$

This measures:

> Given the library actually produced by the full curriculum, how much computation was directly spent on non-current tasks?

This is closer to an **accounting tax under the realized full trajectory**.

### Independent canonical reference

Use externally specified library snapshots and configurations.

This is useful for benchmark comparability, but may be less representative of either learner’s actual trajectory.

These can produce different answers because the cost of searching a task depends on the library and search policy.

# 6. Conditions required for the oracle equality

Your statement:

$$C_{\mathrm{full,oracle}}
-
C_{\mathrm{optimal,oracle}}
=
C_{\mathrm{tax}}$$

holds if:

1. Both runs use the same $L_w^{\mathrm{ref}}$ and $\theta_w^{\mathrm{ref}}$ at each wake.
2. Neither run updates the library, search policy, recognition model, or configuration.
3. The optimal run’s task executions are a strict subset of the full run’s executions.
4. Task costs are not affected by execution order, warm caches, batching, or shared amortized computation.
5. Both use identical stopping rules and random seeds, or costs are averaged across paired seeds.

If full and optimal “oracle” runs use different frozen trajectories, then their difference still contains state differences and is not pure execution tax.

# 7. Better terminology

I would avoid “oracle” here because you already use “optimal curriculum,” which itself relies on privileged knowledge of which tasks belong to the next rung. “Oracle” can become ambiguous.

A cleaner $2\times2$ terminology is:

| Curriculum | Adaptation |
| --- | --- |
| Full learned | Full tasks, learning enabled |
| Optimal learned | Current-rung tasks, learning enabled |
| Full frozen replay | Full tasks, fixed reference states |
| Optimal frozen replay | Current-rung tasks, fixed reference states |

Then define:

$$\boxed{
C_{\mathrm{direct\ tax}}
=
C_{\mathrm{full,frozen}}
-
C_{\mathrm{optimal,frozen}}
}$$

$$\boxed{
C_{\mathrm{net\ mediated\ effect}}
=
\left(
C_{\mathrm{full,learned}}
-
C_{\mathrm{optimal,learned}}
\right)
-
C_{\mathrm{direct\ tax}}
}$$

And, when you specifically want a positive benefit measure:

$$\boxed{
C_{\mathrm{net\ learning\ benefit}}
=
C_{\mathrm{direct\ tax}}
-
\left(
C_{\mathrm{full,learned}}
-
C_{\mathrm{optimal,learned}}
\right)
}$$

# 8. One final caveat: equal outcomes

These compute comparisons are cleanest when full and optimal curricula achieve the same endpoint, such as:

- both solve the top task;
- both solve the same number of tasks;
- both reach the same target accuracy;
- both produce libraries of equivalent evaluated quality.

If the full curriculum solves more tasks or reaches the top rung while the optimal curriculum does not, then the difference is not merely a computational benefit or penalty. The systems have purchased different outcomes.

In that case, compare quantities such as:

$$\boxed{
\text{compute required to solve the top task}
}$$

or:

$$\boxed{
\text{success rate at a fixed compute budget}
}$$

rather than comparing total cost alone.

So the corrected central relationship is:

$$\boxed{
C_{\mathrm{full,learned}}
-
C_{\mathrm{optimal,learned}}
=
C_{\mathrm{direct\ tax}}
+
C_{\mathrm{net\ learning\ effect}}
}$$

or, using a positive-valued notion of benefit:

$$\boxed{
C_{\mathrm{full,learned}}
-
C_{\mathrm{optimal,learned}}
=
C_{\mathrm{direct\ tax}}
-
C_{\mathrm{net\ learning\ benefit}}
}$$

---
