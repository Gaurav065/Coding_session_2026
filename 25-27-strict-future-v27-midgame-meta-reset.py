#!/usr/bin/env python
# coding: utf-8

# # 25/27 Strict-Future | v27 Midgame Meta Reset
# 
# **The dominant opening did not fail. Its stale continuation did.**
# 
# | Frozen evaluation | v27 | previous v26 | Seat 0 | Seat 1 |
# |---|---:|---:|---:|---:|
# | current inner | **28/30** | 16/30 | 12/13 | 16/17 |
# | development outer | **29/30** | 14/30 | **16/16** | 13/14 |
# | captured after policy freeze | **25/27** | 14/27 | 16/17 | 9/10 |
# | actual three v26 losses, counterfactual | **3/3** | 0/3 observed | **3/3** | — |
# 
# `25/27` is a local strict-future counterfactual result, **not an
# official Public-LB score**. Recorded opponents replay their public
# actions and cannot react to our changed policy.
# 
# ```text
# same low-entropy HIRE4 opening
#     ↓
# replace the stale continuation from step 161 onward
#     ↓
# one coherent 719-step route in both seats
#     + actor-local WEED repair
#     + existing-SELL-slot price-impact ordering
# ```

# ## Machine-readable attribution and contribution card
# 
# ```yaml
# notebook_history: Kaito v22 → v26 (this same public Notebook)
# observable_route_source:
#   team: Ezzzzzekki
#   submission: 55390428
#   episode: 91493566
#   seat: 0
#   action_sha256: 9080682756f5b9fc0f2cae25efdffa69474d40883f693b49f58be2c1893ae5d2
# new_contribution:
#   - separate rating warm-up from strategic decay
#   - audit all three real v26 losses at action level
#   - measure the current six-family Top-30 opening distribution
#   - reject a higher-inner-score seat router that failed 2/3 real losses
#   - freeze one coherent midgame reset before a globally later gate
# runtime_route: same complete route in both seats
# runtime_identity_fields: []
# runtime_opponent_private_fields: []
# mid_game_route_splice: false
# ordinary_sell_create_delete_resize: false
# ```
# 
# The 719-action backbone is credited as Ezzzzzekki's observable
# public replay behavior. It is not claimed as hidden-source recovery
# or as a newly invented production schedule. The contribution here is
# the diagnosis, time-separated selection, rejected-branch evidence,
# sparse controller, and exact production artifact.

# ## 1. Was v26 actually losing more?
# 
# Not in its observed public record. At the frozen audit:
# 
# | Submission | Wins | Latest 20 | Mean margin | Close-loss share |
# |---|---:|---:|---:|---:|
# | v26 | **87/90** | **20/20** | +18,415 | 100% |
# | v25 | 66/93 | 4/20 | +6,598 | 15% |
# 
# All three v26 losses were seat 0 and close:
# 
# ```text
# episode 91375701 | Arda Ceylan   | -3,868
# episode 91397548 | lemon13418    | -3,465
# episode 91412066 | Hajime Tamura |   -747
# ```
# 
# So a lower displayed rating did not mean v26 had a worse win rate.
# Each new submission started from the competition's low initial rating,
# and rating gains depend on the two ratings rather than coin margin.
# The [official evaluation](https://www.kaggle.com/competitions/kaggriculture/overview/evaluation)
# explains rating-aware matchmaking and win/loss/tie scoring.
# 
# But the user's concern still exposed a real issue: against the **new
# current opponent distribution**, frozen v26 won only
# 14/27. Live history and current
# counterfactual robustness answer different questions.

# ## 2. The Top-30 opening has almost collapsed to one prior
# 
# Modal Day-0 public signatures across the frozen Top-30 were:
# 
# | Opening signature | Teams | Interpretation |
# |---|---:|---|
# | 1 COW, 4 SHEEP, 5/5 seed, WHEAT 5, **HIRE4** | **14** | post-v26 basin |
# | same assets, **HIRE5** | **12** | v25 basin |
# | HealthStone HIRE3 | 1 | private continuation |
# | Seb 2 COW / wheat-heavy HIRE7 | 1 | counter family |
# | five-sheep carrot branch | 1 | rare alternative |
# | old v23 opening | 1 | nearly displaced |
# 
# **26/30 teams now share the same 1-COW/4-SHEEP core.** An opening
# classifier therefore has little information value. The next edge has
# moved into continuation timing, labor paths, production mix, and
# market execution after the common opening.
# 
# This is consistent with population-level observations in
# [Two Private Bots Beating Kaggriculture Meta](https://www.kaggle.com/code/revanthtambisetty/two-private-bots-beating-kaggriculture-meta)
# and [What the Top Farms Do — a Live Meta](https://www.kaggle.com/code/cjlcjlcjl/kaggriculture-what-the-top-farms-do-a-live-meta):
# a public opening can become a prior while different continuations
# retain the real rating edge.

# In[1]:


import pandas as pd
import matplotlib.pyplot as plt

comparison = pd.DataFrame([
    ["v26 current inner", 16, 30],
    ["v27 current inner", 28, 30],
    ["v26 development outer", 14, 30],
    ["v27 development outer", 29, 30],
    ["v26 strict future", 14, 27],
    ["v27 strict future", 25, 27],
], columns=["policy / split", "wins", "games"])
comparison["win rate"] = comparison.wins / comparison.games
# display(comparison)
ax = comparison.plot.barh(
    x="policy / split", y="win rate", legend=False,
    figsize=(9, 4.2),
    color=["#94a3b8", "#0ea5e9", "#94a3b8", "#14b8a6", "#94a3b8", "#22c55e"],
)
ax.axvline(0.5, color="#64748b", linestyle="--", linewidth=1)
ax.set(xlabel="Counterfactual win rate", ylabel="", xlim=(0, 1))
ax.grid(axis="x", alpha=0.25)
plt.tight_layout()


# ## 3. Same opening, different continuation
# 
# The old v26 seat-0 route and the selected v27 route have the same
# HIRE4 Day-0 queue. Their first market difference appears only at
# **step 161** and their first
# farmer/hands difference at **step 170**.
# Across all 719 steps their actor-plus-market distance is
# **634**.
# 
# Planned route totals illustrate the shift without pretending they
# are a causal decomposition:
# 
# | Planned quantity | v26 seat 0 | v27 |
# |---|---:|---:|
# | purchased WHEAT | 380 | 360 |
# | sold MILK | 218 | 241 |
# | sold FERTILIZER | 245 | 235 |
# | SELL orders | 171 | 168 |
# 
# The selected route purchases less wheat, schedules more milk sale,
# and changes hundreds of labor/market turns after the shared prefix.
# This is a **coherent continuation reset**, not a late splice into a
# farm whose inventory assumptions came from another policy.

# ## 4. Why the tempting seat portfolio was rejected
# 
# The first inner screen favored a seat router:
# 
# | Candidate | Inner | Outer | Actual v26 losses | Outer mean margin |
# |---|---:|---:|---:|---:|
# | fixed Ezz route | 28/30 | **29/30** | **3/3** | **+9,591** |
# | Nikita fixed route | 28/30 | 28/30 | 1/3 | +8,804 |
# | Nikita seat 0 + Ezz seat 1 | 29/30 | 29/30 | 1/3 | +9,212 |
# 
# The router gained one inner win but solved only one of the three real
# failures. Fixed Ezz solved all three, tied the router on outer wins,
# and had the higher outer margin. v27 therefore removes the seat
# branch instead of adding another expert.
# 
# This directly corrects v26's local optimum: **seat-specific validation
# performance was mistaken for a generally useful seat mechanism**.

# ## 5. The sparse controller still earns its place
# 
# Route-only control versus official price-impact SELL-slot ordering:
# 
# | Split | route only | + sparse SELL ordering | Mean-margin gain |
# |---|---:|---:|---:|
# | inner | 28/30 | 28/30 | +1,115 |
# | outer | 28/30 | **29/30** | +819 |
# 
# Most gain comes from the current route, but the market layer adds
# one outer win and improves margin without changing production:
# 
# - ordinary turns create, delete, or resize no SELL;
# - SELLs move only among already existing SELL indices;
# - BUY, HIRE, seed, animal, land, farmer, and hand plans stay fixed;
# - observed actor-local WEED is repaired with bounded replay;
# - no opponent name, team ID, submission ID, Notebook, or private
#   opponent inventory enters runtime.
# 
# [Structured Economic Policy](https://www.kaggle.com/code/pilkwang/kaggriculture-structured-economic-policy)
# remains useful context for reserve-aware control. Here the promoted
# intervention is narrower because larger market-maker branches did not
# survive previous fresh panels.

# ## 6. Chronological protocol
# 
# ```text
# snapshot A at 2026-08-10 01:28 UTC
#   70 unique public episodes, then-current Top-30
#   oldest listed trace → route donor
#   next trace          → 30-case inner screen
#   newest trace        → 30-case development outer
# 
# freeze at 2026-08-10T01:53:37Z
#   route episode 91493566
#   route hash 9080682756f5b9fc...
#   global cutoff EpisodeId 91496460
# 
# snapshot B after freeze
#   33 globally later physical episodes available
#   maximum unique team/seat matching → 27 cases
#   frozen v27: 25/27
#   unchanged v26 control: 14/27
# ```
# 
# The outer split helped choose the architecture, so it is explicitly
# called **development outer**. Only the later `EpisodeId >
# 91496460` slice is the one-time
# strict-future promotion gate.
# 
# This follows the panel warning in
# [Beating Your Own Best Agent Is The Wrong Test](https://www.kaggle.com/code/dariushafshar/beating-your-own-best-agent-is-the-wrong-test)
# and the paired-seat framing in
# [Kaggriculture Rank Your Agent](https://www.kaggle.com/code/raykkretzschmar/kaggriculture-rank-your-agent).

# ## 7. Two strict-future losses remain
# 
# ```text
# episode 91498290 | Nikita Lugovoy |
# candidate seat 1 | -312
# 
# episode 91500868 | Jince |
# candidate seat 0 | -834
# ```
# 
# Both are sub-1,000-coin losses, but they still count as full losses.
# The sample also contains only one wheat-heavy counter case. Therefore
# `25/27` is not evidence that every private adaptive branch is solved.
# 
# [Breaking the Tie](https://www.kaggle.com/code/andrewsokolovsky/kaggriculture-breaking-the-tie)
# and [Adaptive Queue](https://www.kaggle.com/code/blacklions/kaggriculture-v20-adaptive-queue-public-experiment)
# motivate queue-level responses to convergent agents. This release
# does not promote a micro-seed permutation: only the complete route
# and conservative order layer cleared the multi-team chronology.

# ## 8. Exact artifact and citation boundary
# 
# The production file is **20,813 bytes**, contains one
# 719-action route used in both seats, and depends only on the Python
# standard library.
# 
# SHA-256: `f48c21166eac68d1b05a401f04f94a2eb6154e65415af64893672365ff33c7b8`
# 
# Research and generated artifact matched on **5,760
# / 5,760 actions** from four full public
# observation streams.
# 
# If you fork this work, please retain:
# 
# - Ezzzzzekki as the observable complete-route source;
# - this Notebook for the current-meta audit, fixed-vs-seat-router
#   ablation, chronological protocol, WEED repair, and SELL-slot layer;
# - your changed mechanism and independent future window separately.
# 
# [Source replay episode 91493566](https://www.kaggle.com/competitions/kaggriculture/episodes/91493566)
# 
# The cell below reconstructs the exact submitted bytes, verifies the
# hash and archive, imports the artifact, and smoke-tests both seats.

# In[2]:


import base64
import hashlib
import importlib.util
from pathlib import Path
import tarfile
import zlib

WORK = Path("/kaggle/working")
if not WORK.exists():
    WORK = Path.cwd()
MAIN_PATH = WORK / "main.py"
ARCHIVE_PATH = WORK / "submission.tar.gz"

_AGENT_B85_PARTS = [
    'c-pnRXSbqC6Da(Beua+Vf{yb5=3_*}EGTAYjR**eA{iCaZ@(CDyJzNvyWaKg4{o3<byam$SGD-',
    '{>(?EU^l+B0^RgM)@+RZiii;()<vluY@TNylbWf96E_IQ!B-',
    '7IQ?_a)@6m#V<c*Zn5mce@znfGwYiocQY2%;HLWXblZ7AuLIM^`M9cYr0HGx>#w5lmk9m@D2>t5bOFi=y(fC@(!M&)s<51{TUzlo',
    '^LqUr{4b$fN3_qJQ^LmTZa+h`{p;mf<#zd|O784UZ&l#T#i;`ND9fqDLf!V<gWA$IA|k%80s$kry6CU-0^k)m@?pe-',
    'I7xcH6^SEsr57&SY5IqX>e?iH!8c;mYwIajQBsJ*s3mqlzUj96nEFIpXbQ&%zNxUVQhEs_Ll0c`7cPPtmkJqN5zyQP1N0m#<&Hes',
    'L%%y6IsVgHOcVJ5Et;_j+w8vU|N{%$0k6ltlK+moIb+ucFw5MzMaKBzm6Q9pSsAFbe~?!F*rvoU&CNs~Nz9%Xc;vzdc;=z!#76_x',
    'SujTtwew$^7IZOU=c3Hmd_Za0*>g1dFp~xIgXfk5vR}nK6bQ_Im3`q(N(hPdSnr-VoPk3fL4g)M2-',
    'Pix|c%;7efYo%Bu}X&XG9QnGfULtg&>JXi(A{M^{-',
    'TYBH*Fn_?g&0Wt#atSxLi4~NM;&34wtt*pe+dn27vwmX0HLM0Ta|~2J%>$E~ANOrxYgxFQ3#XFFi}`4Km}5;l-VvLcapK9w=E-',
    'UTB(A$fjjzvV39av6timm{rdRTn_N6247m-$@KQE?6cp+4-',
    'vtV~Mi3ug#TFt!k2F7oLT%uW1R`%?;=niwMm>Mk9R%B@rT$53MY7)G%>B4UNWR;C7%7w<F(LDe%>9aA`>PDqL@bkPm$!#M~sJhj)',
    'S}lSI=(@K`1f=q6if+Uq!1MWlmQHN?hb9Hk%s4h}%W6Ll4v)wzEwoSPbn+0ZRTF1|4P;e4%SRcdlboIFp)Sb{(MZ4A#~LwaLR7uo',
    'Co6E~oi#efEW)>;-',
    'Z(bv0<m^%dtT7zY5`?ur{=80x?&+qrCSTtR?0$GG;>BogGIW9b?Is~9FPnk2S`{IIyAjn^_+;|=MFO%ou`Xc25qkL18SvNi_x&u^',
    'rvFNWp>6hmmN3~gNuz|ouh;wg2cSdiceOdDLpb9>&0qbPVNh+moFlj@cBd!E*6cYlF1X;MCY|?5rKq6V^@j_`Tefys|9B}S6Cse<',
    'yt5(5lV8^EE-a5$DKEp+L(uN$STjJpeBc}oy}1Jc-qCOE~)ZzWDb_s{t%vC*XQ&^0IK9VF`X`|G+P+XPm=<fJD=wM%BHeHRt+2O?',
    'KMan3Xq-',
    'L`0P9bCl<SKex9pu+QK0;iBY9wXAt3<UUieJZ;gHJ$*Ne%Cy2qC!wnFMkQ$JYhZRSYz1=u^jpGwQPx^`AferAROOY$O0v5#ZJT6k',
    '%O1jc$_oC^(73iGiRN-',
    '`<)8;WslQ;^p#aPqeu>n%1J6)=qW3M1u9Zj0iv0gmyOJ%*Bh0+KSa)$QidV^WhbU2xqPU^Er$K?}~)q*zV=~`@^cAqJYXn_jFz3t',
    '3dO7%`6PK{dYRWnVrxK61yuP%UX-`5T(4bn^p!F@$s&`rf^Tp@*?ACIX*L7Wk}{8-&>8-wxa;@{4V7}CgEFakI0hDnFTMd-',
    '<Dtu>W$5zw#{lP!$FEAGkwUKd%uyj;ar3?MhU?fIgtgtmU)GJk;@O<+?#A(L6r9^usju^bh_^;m4er>&3Q%DT}ED<N;j9&I`+IGh',
    't|W-',
    'oY6@1=9azVwLNQRTsM!w!v}tdapdT(rCA+^FB{9<Jr__2eV37nP|bt~GWLIQq0Ur<W&_bUSF7VF8iw)B)Pp2Q&wT&HUmpGP>HnS&',
    '`VVRyl<>9K6ZC=5fx36PAx#pkx$pmXT^S56zNV-GYoglyU4P%J`lTkC$_5EX2b5yqVkf5*MaFiOsJQIC;&S;BlPW6U%&&BRlz}1j',
    'zfgl3pWVVjp6bD;3GhPgcFoY6pf|S((gi=xpwIilJE>DUML<7_+Lh(80N2Y&r;aJDRswCH4|e(wiZe<Y@E=5=$1CT^Fv{_&$s*8$',
    'G(QHj~FZD3wN?p?qqd7Wp{TM3)+(Y}gfJmdao$-|Un1W_Q@Q=5&9--',
    ')eX#alBUGmp=5Es!moclkC>XBfkJ=l~|2KxKlRN+>bRkCg<P<o6fn6JDf~_({Mo7+GCpRQHd3CRkU<zWe=8ZYUP_shgfjZKn0Gfi',
    'K$v|7>c46vdRLN79Vde&s$9Oatm>g2<OLWH&*t}2F#!|0Y_-NE;>2cYYT>}FHls)P_BT7XOTuE7l<BJrajUweLdX`>hm$G6G1sQU',
    'orJ?bA7g`Jl?QaJ+kWVPBzy|2c&A2Uqxo=#x)ek`4T+{Lfl!D(mS(<wtc}RVs^1kp|5mzc{CSYNJg)V#0x<Z%8k;xPsfO!wwAcP-',
    'A){hSf8m9;a#7q&YUbUJ9p_qZwnN>#Th&TtO{llG36YlE8dLD=fH7clO#$#XYZ9oFirJh74-',
    '^plj&im^@+Jp_S#C0V}KJ{nA+AHJHafMx-QsY$STB_cBf2DNH7CaMKi0VYonFO(RC`e0KqLZ_LIj>Oo~2PNytRErmI0gMQ)zlBho',
    '$}8;_iP*;vwCjwbU&4&(i@-pNP%tE4yTmwT&;+B)^KgPng8K7kB1E7Yq|r8t-6seq2-?j%O}d?PrzP8nTaR7cxdd?c(?$-',
    'GW;mmWNm3VVvkN=f)^)z2tSZtY!uy3DIonOzx414~`FJ%aZevuum)F8nOQ6S*U81S@bG&KMH3Cyv=L=0>}=xlLY`Kw_2Lb*gn6#k',
    '};DW7Ef42|6B+wnz%|Y0^LByXjfJx*Up;;w0SUTuHOR_2^Qcoi{;x?Cthgb~fBqwaqRQ4GhxlG#3Ws=op;U_iLjtnDbal?1f+vGs',
    'tO`nQkU}G$07$?%a<kE2DwUPAb5SuGQMsPvIp~*_D+jm3*@5>S-',
    '>tRYtvH+!_I?Lx2JI2Ue>@#AZ>ev9)RK(2Nu8b{q{jTjG?Y)OX|J_H<okw!&msDeP)7<kXlPdx7?>K8)o$<i)p-',
    '!R7j;)9{ygbaEV&o~)vAvDHb%VI9X0s*NzMk}hqcf?4aq>-}`Qq>5w?R~g(gE0%-',
    '+R6aPDLA$?VGGzc!+sks))eoaGkld)28*x8TI?+}d55<y@7VoxWXD$cYDpbIPdb&1DE9sHVW7nxq%`P)7(#)1rb^xJz_Q+Qdqf&-',
    'Pz0?MPYL$aad(#ZVPSp43R}=sI7)s7#gWQ2iO$x)bH#NUTYCh~bYGeC;gv5&D&{-',
    'Ykc}9zAr>wRGReZ1!+4gn@!m83WwoGn$U0)AMc)i;QL%*1S;C7n_pR5*0NRBSX_!`1=I0$B!6T7Rl#(tX%2nIrE>3ubRPV+1<=|i',
    'K6&$0r+Y`)0gnWW-M8yK|?os?V}SE(t@#AnJzvN?TK#Y5;`Y9eL(igo!;SZ?5_DUEcZ-',
    'H7ZJge91kUXd`aq5?4<oa#FyLC6#|2{u**UsflKlR7~I@f{P(_64)va<rxlupqKug?iAiRm=|3xu{jEUYA$Z*&T0v$-',
    'PSxTXK`x^4J<3i;OUDkN9IrMMM*+&HV@K&|g)M!aTUk4i-',
    'hqJY`wA90;#krS!5!DviA=uEIXL+s<~^#ift%2U6F(39T*i+!c~SbZvS4)QGd6toluPR37D4!CGaq$*z#XA?^n^OF@~ZVCE3ol;)',
    '!lfgjFOG|h>XPHVZe$ohq(F40o01&y#!aWP(TVy-',
    'd04y(nYdZ>iCX{%;LPb!6b0R<v<3wIOU!49eY6dQ&iiiuGAr8d}3#*JE81e_`WPgUzuY?X))Gl8^RTv6#pKq&}4do!6)%to#|9_i',
    '|*PmO!2k%6_5-grpwL4zy?Ix&*n8%a>0D!XaBl8zTRw%CZ54uSnClx=4RtJ5@GIS(>2a5*;0!-Q1V#ZA@-',
    'k(t_LKx)Hm)g^zzXg+zaVxWm8dH}BFL<w3hBl;{U%3WmG>KE+nI@+!I1f0lr3PUe;;6$%~NVKw*(RvE4M<p+)3|obOC03QfF;yQ$',
    '_q#)|u-',
    'rpQwCLNs0@aAOLLh9;iDo&%Fk@@S`}u8#3h$NjhH>J~rcs|~TS>$l*yt3|pQfpKP5?IBO~4;)qv2XIRcUsPtf*xRLJ@&il~XNEWb',
    'Ht+ezjj))cP)Q92-<B#tHCx9>>!`3e>8F!%^MRQ=RvzUMLAKQ>EZ^&`DoxbT_FI{LntEMHO?2n1NjNSfW?-',
    'V2#8RT=|*|n3%6sIfiTgJxZwMzU1|;#Ts78kb5bUE=W-mr$KceEo4L9Elam!=*YL*!0j#`ECrC%da!+&6A-',
    'pof7dB3utB%oO*NV5fNE(=8Yb37??zq?Lh~BSwj#0=uIICLqEYb=GkY^La|++W@vwzr(P~XsNZYs~!9=2g7p9rhD1(^U6M)r%<T*',
    '#7ZV{qR#Xhzw9Fu^)9bM>pG7|}Vqo7X?rNZ-4iq0lhQE8=XR==UnV#Rz>FO*o?FY3anzpn#@eVu%HVH^<FkO|F{vwdm@uJR^zh-',
    'V<!Amna|o-',
    'rZ8cbxd5=%pMQz}tYajV7r6CI~_~0$u50m(0)v`bmHrAL}?*IyIJ55|O56^4t%kkYX)%_Ty$DkB56Wm(6;QMg|W8{Q?s8D@BZ7Xk',
    'JY^hDxbUDA~w|u(lDG8#^ngX+B^mid|sr4X<$AjhG=Z6&hmHA%b_ZbOb6cL;L)xp;SP$P1y-8?XPW8oYh_f`x6q~d41D1E=#k-',
    '#MfYVOK(pdS?x1h2;%ufqAQsig!SA>=mDY>07e6}5d)PeyBcMohJuWI<rt8dO%unaIp-',
    '$(o_*FELtzN`PKWV!UV>WfX1LHu`qz8b(lSz5WOn|8%#HlPS*1{IE)%<QBbXX9+G;l<o~&l@+$!g`(4dq~qe6en_O{(!5}Pm`(&%',
    'MEUAWTsodCWR@wK9rxi4lwLBI}YW{HYuUOQSYF4yQpF-',
    ')b9S~(tUl@<&!+iZ`KSfQc7?tECJ*&Fn1usg&;(0**kQaj(U#rRq=AC}V=(a1<>wEW663$#U&EtlaV);SIFw%O;xnXOU4gDbIUCn',
    'TCK4<dnUS;q`#1L93y#o3F693SFfEH$M0NpFty0z)y-I#kJ3gYWFc06C1e%S@!^_qMLXS-!jLi7{G8lW9TlzSed-',
    '(dc@sxsYAhZ_k0)d=~JExs6SQe8Jh&Rzon0n|q6xF6LvEDN<<-dbJKl`C_9H&&P-fU-',
    'v_m;#v*%+UG*3gN%fFYaLz-v2JbRoyA+Joj(S&Qf*X;CV(i^<`S_^3JS#=zU-9t*L^W-Jix&m1nw{0bvoH-',
    'ALfbJL7erUtcX0WCY-onAl*bM!5;}gIePocQ_#L{I0Eu@qy0i95Q?C$s{cR$I+obxidQy~lCQnid~PjQNPiix@^P`>iCQg_XQL!~',
    '0HN3b$C6!&on-',
    '6TP><<oXDD>VNaMPxp4oaL5z4OXGUA`AvOO&Z{B2OUwi*Yw+k&0EOF@lUXjwI4DMYI!HkUD*@sGOw9h}L=g<*E$J6+UtsX(^LYNe',
    '&2em_<Spkq9j#)3nklvwX_2|w1Xry}Eqy7yPL?4rWXGm~x-',
    '*I(s(vvDNtU5ah?d;>8qRe;6G@R|q~1Grd;_L*V0Z1;EmZd%@3x^gCB933@_;IfxFYD-EOIaNclR|Qj?*JyzW|H2wo7n8+0A3x+*',
    'qfQBrEpqPWjuDuPc{J*i;IW?~y_P(U2%BuQ6zol;<gl2r7S5th^nK;S;0l#;P$knC4*F1-gYESoWb@T6ySO5DT?mwh6*ExYjB-',
    'lUD4von^|Tx}O<wW24G5T;pGj#vK==Ze8H-6@pg!qEb8tC&?Me-JyU&G<>mtyuQWt2Ko5zTxmm--mwWytVpBYavJ(Eso_$HkQT=a',
    '^9Vr<OYU8FC$?w+B%L?>%PPga(l$#}i(QXtgO;_F)bn3vby)BYlLh>I>ydP?EarMuMuEc9KS??#7uV*_-0j*)zGXLs!l*;}-',
    ';kH7$0M2_SkgJDhowj+}i5{st^8Z7yCxU|{?rke<U+@`p6N@`z(T>?C&YV|-7VC^(rEwjN9W-',
    'm&yykWZ~Dk(*?__m=b(;||3d2y;)jSbc|Jtc^;H+;0>K+fPr#yd%*N*&s$hQrbo<+_7@bGt`R464D*P;Z^3!@6!;u^4_?F0gG*&X',
    'qDHz8JoquK9)tkm(wVoJ*jUZ4KvcNDS7dzTTY15%`+)O~X_^gbxnaqOQ5JT&l^oZO_udrdk{124u8{cUnib#O_8bRY)D1FxhUmeE',
    '4L#K`<xvn>D3u>lI(;ieF=4ahHX#<~f(#5y6bG7>(-?+raY|COwX8=Ae2gsH+z8s&zYb4^i{4{c*NQ3&C>$m<^dI3Qs2WR2ST-',
    'G8Af?w4;;WrC7cM@tn7!!|P&^-XB-zA++?tVCsVM)p#<`D%G}rmD*ucfyYSK^yez4&S+y2R~XdC7B+R$8_ca=HO{nQX=lAIoCZ{X',
    'f~9Lw(95Q%>_pOYOE8)4bp#)$Nl>ZPj&2~LXD3MwBgAX42riu2)}twB_b7=fo>J=^mge^HIm&1Dg*>=|=FJ0$AM^2!Yke-',
    'J()y_!&czz7Ij$}h0a~p0+%VN(w0@<~56vUP@_tz8!M+}qO=uH+JHz&yT}KZx{88;m63rbNk!tx8%_q(C<*W`);39~x?KCk9Y^wE',
    'b(6wVKIOh|iVS5n{9|5dS^+LkgG^hbGkYeIa6Z*73R)Xq^-',
    '5w{Hy_ZUAq2kZVNQ6eO{3~0x=3cQO^OfBSI@oq;9%uoR>bi<u)Mi_b+xWJ!8|9dE+-',
    '`;$f2bl^fly&$aa<_aI8O>`J_^B?{i+i!x0+)Wi~?P~>;<;vgQ+&Ircd)NGep@nKc;C3A*7qLHrjPch)t)&lq_v{T`n^lO|f!7W!',
    'a4TN{DyE%v(Vu2`782#(|jZ7`xUx?m4_T93qu@g8SHvqKTQ-8jVBCbd%zyoVq(OsWGfJQPF1Dxm-',
    '$Y7TzGh4Vv_tUR_~kXQQF&aue#xzzL656J&3S*SlfOUM`VI6i@MZwRIs$){3G4+)N%O6azn5@nfz-mNLpJBN^esxzDF8ve~MsnPG',
    '#S_t0QRYiikju#Ssx5+TtVmRV{u<cc2PXlPze)znQT0P8**Y$ULNoEukrO?hg>fs?f_OPA4f)UPpaM&=T=Q?}WNj6fh(;zw0)iSO',
    'xYdpPZ*=ggGamZ#fQ^BBZZ4OB4Ao=u3cjTa~91_>8a-7T0nc1x~`5^UM(j7&U>FZ|%8QZAztd@a%PwY-',
    'd#xs)t**Q5OzFOJ|*A>a46EJmFTmTYb=QngXp8!QE@Cvk}&-sM7!CAnCmLNs%5z5vWC-',
    'l3*ZBzz&=YAG>OH@qlk#N}=WUa?#(w>XgcrC!ycl;t<~1hO7F8ANjmR3NVPM={ySNsh&#QoN&$o9Y~_Pt%R`(1h&@UERs^b`5COm',
    'BLsi@ynuhTqWHe{ZT4u=iQ)EE@0|1T+A^IU12*hamJ%E(%tzvqgt@`M%d`~`y{uVU6a%(%Iq5}#DB5(MJA8?d(q>ne35%;nva4aT',
    '~>YhZo{k|`I8T5MZ==zT0=M*f`ADV6RYSQ``A6#(Xg@Rl$hQ+PIuk}03W+mXid-',
    'K`DuJpti&boRT%W!J8)NSCdhGC#B#%>%%dSoIL^FI$uA62uu&$^Jddp7G?6YwXU^WfU}WR4L{Y)s2#@k!eZ_{Tx!3aNgXz3BDW{h',
    'Nu8;~^q@{keSQR?WC#(G85>-',
    'X0(J{?^vD!LkvnC#`<jMmyy&Co7LJX}B@QAwElr11ro98P!B2JG<Fdm9u!)v>RqH<JEqcDLQEHsg2(TO76anJ1fc7E?d_nkYI+v<',
    '`lJ-7p=YVItT!(cR1wcE`eW;){UcOx&RVL85dVp@%A;^-af7M&9E;%M55ofi`$sSKAQ#tLT+r3UR9boPxe11Q%|<S&_B*-',
    'D#azbUujq=tZ<3f?Yc!Mxj@AA(NR>UE-S7KwzU0RvR?wwXK#W;%<S-B@d~HcCXjBd0ogpoef8Lz<-',
    '##Dc5TQpf{xaUm(}>QFn5h2SPnMP6r8NV!_i6o3!`h@oEPXy-$1K-',
    't6!mEojpISDtoXpi~HzP<xd*&7pbl|+1#V~miX3ga~vogXjD&N{L?$`m<2Cld)cpztMMJM_wayJEpf-0Ph_Nw3fan>sY&Lw3EDl-',
    '^FQ^ON}@unQSnze1<jnL+>wTVC4>JV(6Fcxs_#i0m8=?RYSrWQ}&C#pw)i4#64yQ10!ALMup^jcV8I27SD80uLFsS4nxZ#~9Zs6S',
    '*d{^l#!e*-caXU2-',
    'xD$a`Xy$fA(YFSq*f?CcWvy&C*vFoYyr&S87B#e6;@uk^2G1z+=8uW(){nXZ39^v(0C<HgF{y3k53(PKge;Mj563N%wqWNY?2y*w',
    '?{!igAPs`f6~Ru>=pn}JlFwzK&(mJGf6;z@jtD?z(fv&~s6(DrNkz+QR__IQcPdvS%~DJ&kZb`MmV7%odgCQa`SEH&^7QS>B);Ak',
    'JEWYL_Ld%;rskU9ZQ2}aD~LPAgVj03*uE{g6(zb!FUJH;lid<<_+d77_JGcw8IvzT>GpI+Td^eiLi83p*nXxJA{m;)l*$WGgG?0T',
    '5yD}hA6JQ#W5tQJp28zx_@ISJszGa;MlETtwGGZ)2t50;BjH4+%l<5sP@8qf3D#pZQlLj^-',
    '8F5Jt6(``Q?2NlidpPdv0f_Iu%$X=Y<CYN)FN9pTuR0l^~ISy&%uqpPaaO_mx4kzuJ-fB1O5?v{F^SmrYletidE$UT1zu>AssK3d',
    '&n+1Q~+w>Cc`eh!78`EBEmE7gJA>UEy@GA@2Cpx9hsR>2*9j(MBv0ltvPg<<l5xXm|mOR;seL9H`PsUc;!~?ApoHBt`B~>2Umu_-',
    '1*|xZ819-B^EF^8Lwu?qsACDn0lQ6K+K0cey`UMET#sd}Y(oSef4~ZT5tRaT>q+ADAVy8LC<T`^=tUl`DsW_DEbgx|v-',
    'X9dU!0rw@<7#b|FpDVJ9)(o6Lkp*C0qZr!L{u1Fcd1%_ks9Q!fz=+a;MZvdecg(rbdH6aqoLZ*WS7=~R6uBHhzF~9&G*+?yjrUG@',
    '}*XNt92{b81L58=WA+n6jL3UmBdAN+BJ>-',
    'G#waLhV7bG*&ORm&9}Ui5Gpra4dj98ZuDs?lVZCOG#y>(Gjrps0$d+GB})YD537AiZONupK`HNGSuM}FRXS=0H&{dw$KwKY$c{)N',
    'cd1F!3ZQ3+;=F_&Np0@ka0b^d>COGh*Lt-',
    'K<dz}!+3`lpH9IzSI#J7W_y~#v#GDCeYvv<}=mwbetsudRO#lsnr52d3`NGKX;A=+$b8-',
    't!>dE?&*#|D8RADmYTQo>{wT$F)AWqfkp|Kjt3de-',
    'n3_P{jQee#cW4%DNdI78co)}mpo0r6zUj%}+!)dfgEBPr{F3r!|6V#29wdoc1j}G36Oa?3~>doTobbmqFrRwN}1}8+xEmW)iS>QU',
    'H2AXXupeIz4+T!6d(9+D%uGWlZLa18Ju@WeF<@Bmqj(9iSZcSABd#t+853^b(?&qn{A`dY+qhx}GO<CFJLEWj)UOo^gNR^PEn5p&',
    'sg0QR^Y&7_Ve{<P@-n3S&RQf{EA0-mhh#%H-yDkM9NnzbpLr0>VS)+q0QD9ZIw?{5PRC4U=swf)pS(I3auc-_u#io1l+U+ZJGYnx',
    '^xYh1~wlB`6dZ(cc6YU&V7<R|?bCJi|OKmx9onuOMytc=i#;lq1S+)7a%I|S79(a{%^#)eMlg&^sR~!SIpuMt=l+meW*nMkJ710D',
    'ejPGWA-',
    'wXP$iGC`c^9oLkuTFXsXnF!E>l*L}@XOquWum*On9vK(#?>Z9V*)rQO5+A}s*T+3)cJVg@@t;XD4Y}LGZ}as>q6Z~<=EAm-eW#j9',
    'mS9JmLF|Nbv0<IB3oTYrDJ5GVI6y%B&txkDy<n`k*&;~`Yg2YPIp$PAW9H@;7K`fKG$vcL@!4#{X-',
    'hhL6Q7g>*ets*sEa8$r9COyAv>mQi$ItW%S}iL0eTB=45Yp0VP_ytzWPNUb=WsG<dGGy2yUI36A&4qc<E{M@&j5{n@B2xXMc|ip5',
    'f#s18kVlIV#2pq*U#NN6rEOl7p5Pbvq-sq$<mcdD7`f)W`lzpp1dNI9O4=Om-r43no|zi%}yJ0L~2-',
    'E~4Zy0ov$E7w(4Xiwmp^8=6UH+eMO4$i{rp`E0zgC-0j@I>iumocJS!$?`eyqtyCyunL;faEfbZk~*%YGiy)TGMFF$>t-pgQL-',
    'AIa4|)aX%-kRrgd;nXX4C_!_Jb4Rf}t&JNH@mUffECK}KCIvY8I_=P$q96JM@S#D%7n~Oq>-u6YeChaforDjfvQ-',
    'zY5ix;tCYa@hvwIrYQckTFSHOB&nhCOgQQ-zq{*o=KgZ+z6RcX><><*I}B+=yAcWKL#+4*G%hp?jshJTodx$w4IFy3CT(Z9VRbDf',
    '{i5JOD_B_4dhh9n3`sW{Bv`rey$)l&K1x$iKeAG6nWJEJucNW79^jfnmMzIsg!gPDxm2i#{`Ogsi6SKh~2quafkov{I!|fx1;`oU',
    'zY_TBp-N**8_?3S81tT{w5J%HuKKZ0xGF#Bc}@+o)~if}}u!WQc^)P2V(`-',
    'W`VC(&@=+KFeXv%z@k~{#Gcv2&UW9;8+dxN5L5$uGfMKAk)i%{gTm5wxk*93tYD6F?l@}SmPS9mjP2*WEHKjPfd;GzJf2)J+EIsj',
    '>Y_*&5b$ad<N2PS4c$1^J@ZukJ<GeZ}$@$4JQpLm}qW%^V(*5!aIwQ-2pFst#Ud{=}zUka0*Qz79ZopwItC^sIp{-',
    '0?W1<WhKDO>T20AsI17Ys~IxnT_uuK%#BHxV{*^=?QPZDpf^$r55&r$NrLK+!|9}M#kw>s?dG+qU+}_IXR$8j_*_>PRK2WXuanG>',
    'u9Y`nm&xnlY&eYuPwCMvMN!5n36Q5+v;<pY6lvAP$@IYN_R(&RQ^U4mV|DKUFl=^LvDYa!p9#fz%)1a*jR94Pv7|I#Z0u{e-',
    'V;`nwcE~H<kY;s%r?NDHqrvuRx2~wC7?nF>Rt-_Gdr7$mjhqUvy)j=nM4Mxy$AR8l0aqz#OD|Dc(fG~Hy5Ad={<kd0&{}hS7tc8P',
    'wWbWOw_}Nf#U9hG`|Mgn;=48bJ=)Yjho1NHx7_k(%YB;z=-tX!zw@{Mad`^;Fv(+3PG5|fl}OzY?8_5j{r0}`rx=XQ-',
    'T8Xt+~~=sjM%<RV7Lf50=@*_2hoDr^3ww{cbEh=#Q3~FTK%N4QuT$dW9jk13JMn#}Yef!HXO+s$$7#fmX|z<xXzrOZ~;E$)*5cIE',
    '=2ev{>#JcR;S)X)7%YO7dE5g@o~GcpBZf3XIpWV8YjphRU_WW(0Of9u&4w%!uV<OkdK?EV|wK;^KCu$H(FP2J=RC$e103b{a@bZ6',
    'lRB6SCQb3eVyW`~rgCpI<NiYMDYL^%Vra&=g)mTPT6yZ{Jk?<-4n2=nhqP04gn#q?}>+3th(BC{d=-',
    'R;PwKPoVEe{0rSisV3g1J1B*=Z)8q)zF$W*9PNMo%L5?sZyp$O{=Ru)w~w!erkh{CIoK)ZMpBmdYXtoEz{60ABJYUNH^eyf4*O0d',
    '=_2;YHrgj|hzaP0h}=0!qRcb;9X$4qn{aV^eF`0waEhAT@L}YG0Q_0x<U2L^gFqW^k;G%RAGlHIcd4Dr=m#2Jt=^E{aiYlY0{^C@',
    'cD>cSOZqld82O}^#NS9dBFWZWQ0RS<@jnatVpzece!W$n;?$ij^e-BIzja7lzR<lI*>N0-',
    'EDx~$o0pW(CjL<RT^HY6zj66?>eDHDN4~?{=l$(v>)*gj)PTThbg%R9pwBeFeX_HQGC?VV?)6Cuzhm6h^UWQ+`9DVCX!}EiHxl1G',
    'FM)oM+F1`6T6s`>I`oTXuT7HuS{?sKk}tiZR2!#y&qel-',
    '(4CA+_+1^JC+O(?_WgQidT1ZNDINODbGkUDyZv(qDZJA{Ck_nWxfv$)<;#}^FL>xBZvs0;viNVF4R3$*I1d?1GIN9?^Wa~1@kGHR',
    '8lr5NjLh*a@IvIw=lJbU=S@qOJ@>)yH=6Inz&n`p^!B<z?smbLrtVVu>fAe%x-)e7af~D}ti%Hkq~94mp8tW%$M`#s&v4JF>-',
    '<vO@&KpEg1EGF#uOFVowDpucW@nPolD@ZrB85<*ru|VG5!YF<0Yy7#JDX(1oSBS?ccjZUv-{kq?-!A-',
    'ZkoS$mcvr%)?6t?<^>O$#C{pSHRmF2{gmq_yLc9Pw^f%j&L^!C+_p=?cxb@<9)h(;(dCl@2kM*TV8iuOcD+AiE%fWJ93x($JY+p>',
    'wW$CbkIBIijfzFgZSf)d4GfB6X^Zzl*eOH_Ix7!Kz&gD3I2Q|x@Gi@WByN6|B2EQ{ufdgS7W#LU;u?Ro_cytAATzQVMk}!v7Rb1H',
    'h+&@cUsP8&Pjd`J3ubEn@S$=H^NV%w}*zK`@6tz6z|U+f{s{E>E30ykN&uk`FWG(cHzl-BwhyYBjAJc=`|BZ5|=W4SKLzp-',
    '#i}^dpW?LeB=(nAJoT7KDj%SyPR+H`Op;j%{A?BqTe68GyQvex{LP4=RN{DGjsWWtlaz1cm81V@&fqby3O6z^v%vXBQJU2C3obF9',
    '{6PPkm1LZ|4&D>|K^N$_#c0{w1575x6Fg6t9MhBc-',
    'm3TO;z7Ks$z(5>(12ekNF(FdF*F=aKU~+&Wic`1b&MC#_(Z`2ZOISexFtU!~Xf>@bhUzj#o_&P?s0{0oQd!|K{o2D*wD3-',
    'h$ix`u70&wMAl0y!?tKrp|CYeSatGv%B1!+vL@6p8MEqq7Jk(xhKevttbOq<^bHLc7q0Q>*m|tLQfFTF&GT~d;}lYBkm+`3+okje',
    'iid>zB{*n2tuEn@eTMlxBc=f<%i+#V*LCNDEscJ_jUKd>Zz_h&oAi53u~^r?(4=~il21%+oJrt#d`<4Fa6xx3VdY8+Z%Vz(~nI42',
    'o|m?Z+vc=gl;pv-(>GN4^2pnVbZs!jy59jn>Rekp57q-dfNNzO|l*T^|4EE5q=ZkmarWnFCl-tk-81uE?#l*HiKV+=6%dv4mSh-',
    'cz1u--rqc-k9hhV`#mZ>v|-7j`83L%-XD_Kx3>)Tr2G&0=w-bf|D5d)S2;hwJm%&=-',
    'hJoW&HrTMX=+jah>bh`yJ+%T0|4LDFWwgJt%myJYIykGZB0Gao+s>-UoTYQiJgB$@b_82arhAZyQ-',
    '+bQ^=3al>6uGUQAK8_}4>b$v>^<tlYOr{rKu^^qlJA=es0#U?)F*=KC(vkGrrx-E8rR;BBvSdt3ACTP)-yhb-dB=I*q!x7-',
    '`{{JvHFFAV=Rw%tOL8{ggpF!=wb#+L`&IezoJg8Mzx-',
    ')9EiT!EJ@$Eu9U14mJP0XZ^!GToc)o(}Qh4=<bF7y8pXZugPTj`2VgW!Gt)8(A^mcj>NR-',
    '|prBUl7m7fBmy>Jol$JNGGK|F`c5MG^n@Aw6n1K1E-L3mZ)PW!YPRUh1@O2-R<<}-',
    '1^S;mucKEp0&np3b)(G3f?$+aTc)GQQpmGzW$2@4?Vew;1&-bPX3C8FBg4oj9-TRh>U-',
    'Bz8_!9^{N{tT!(+!^EUno3%VzvPx0$h`uUqp&L<l1U!T(4-',
    '{%^4OT1!K9*~`&_U%!gJ*{=Wc8K57I`rMC?gdF<p0yzO+SAGR{E>Ur`hTwYeuFl&zk&3G{ubkAj$d(Z?_Phu4L#-',
    'hT`Xn!H(1UHto{QU4E+Nl1i;@RCm_9{>x}4F>SN1wSLsX3kGh1uzo-t}^1v-',
    'N?40UQ(e0<gZ|{MB^YEG_N+PR^mIGoqb*}S_<t1fL3zp2e*N$^KZtlb^R@w2-',
    'k;nC8#IYOjk+MJa=6>9`|9o}@UyJ!E%57u*A;4QC+NzRhT8o=Qyi4Gi>n676f36?Bi+Y#-WA#2>($75*!fzx)e?oo}!-',
    ';Mmy87~aY<?H+lM;Rv?p<5|BwXZA!o4GZ=qvIr=%<42wr<{gr;mNVe*0Yl;LZ&MU)~`a&TdbVp5^VQ+VsPWZ(;8a=Omh2C~|fjmM',
    'XbR@~#hgao-',
    'U<i)Ckj5dAcEe}0QKH&4I)qQcid48uQfA^o%KJe|fB`u=kZw81Gl|JcvHi~o$(f1KKT*?SKvUn8O{e0{p3<DU18hYq-sfWH@4n#D',
    'YRx#1b09@>2%AU{FyQ+f0sOCl%A-',
    '5)*H>MbFC6z|Wz!na%J<h_P@Il>eA0e4Rr&ynA7?#4HMLwG#?4f^>57W6x(SF7Un@SEomQ|{f^XT#zXx@IZn&A%V|{s;{>Di6*si',
    '9dy^--G}kJl>*+<m_woU)cO7QcfsvjR}74h}>zs#+;S-N=2V%6?td=a?i()ebA~iuwd+m8GmWf-',
    '6V1g+S~7ge6slM$#2#$R*L$$w{rt?pe<QaxQ$a2-',
    'XVT(mE2}zxWfEn*YF0|;q@|e^Bg30r{es3v8Ug9k2i(9Yzcq+=U!ybLH?x^`JnzJ{`h>T?S8BSy*9QtzPE62pWI(>K~q^+oO$=<P',
    'o4ey9_$9}#3=C7{_VcH9ZD|h=Y83edDzKbpB47M&r`oS1Mms+_J_DlCYSho&kp_s?mF77!F!YbkFDM>?=s(ZlJCbKFLK<y#Y;b%$',
    'DVt))<JS<=RP%dAEF??BLAI9A7=e@do%HGGyi|<KYx}O{EeDp@XsKhRrev!2kI|Q{a8VZy9@vF@Y#fTbyffOKiA2j4{}?Fspw?j`',
    '*FZ8>iDdUzftrjpu5t6yH##--',
    'Wux9;t6?s20x#{;GgFA_m26C3GZ?0CH{Lnd(d#h(>+zaC(mEZ_nt5BP&YUIyOisC>Yx4i?z?YJcw5kSirHto=)WZDJH|gJ=>L?H|',
    '9?)d{~y!kEBZZB&F#?oKPQrpJ%?eu*G>PF@ot6tU4}>F%GtHb++Ba7e5){=@cE?ozo%%<f^jguL!UC`!<tS=d=w?059mWK*^hHAM',
    '&8_QP2Yb>>vQAsPp4h~ewy&I>Tj*IUk+p*Vk`T5WA5c+z<*p0-',
    '#n3LkLB$&=wp?>^<ZAD{g0;0Ly}L~=ohEI5B+>UuDD5hJFP%|TMy4u0e3pz4aF%!b$-',
    'X|2A}KeA622exgWBKx8q0$(pd?2Ii1V<p~j8Dr?UR3uzT-',
    '7<_`|hI|=X)@;(CAW2&FdGafYl{uG089K!sAp5IS(KW(=^x~ZR|@$cUt`87QMO-TB;aQ*AIP<{`|kA}C$J$ZosEz|tzIO3Q2-',
    '8}pcjr~v3Jx<4dUkApI8^2pS`BQ804}$-xG4ubjCf|+<o&^qm|L2T-80`0E``d}$ucDkj&G6$0*ljy~-',
    'hq4^^!|QE_iz3AUnqT??!Jw@jyN~Waw+k&VX<4$Fr4Ypj@Rn8s)+yUysp##jh{QA@c#lW##S}',
]
EXPECTED_MAIN_BYTES = 20813
EXPECTED_MAIN_SHA256 = "f48c21166eac68d1b05a401f04f94a2eb6154e65415af64893672365ff33c7b8"
TITLE_METRIC = "25/27 strict-future Top-30 replay cases; not an official LB score"

raw = zlib.decompress(base64.b85decode("".join(_AGENT_B85_PARTS).encode("ascii")))
assert len(raw) == EXPECTED_MAIN_BYTES
assert hashlib.sha256(raw).hexdigest() == EXPECTED_MAIN_SHA256
compile(raw, str(MAIN_PATH), "exec")
source = raw.decode("utf-8")
for forbidden in (
    "Kaito Fukami", "Ezzzzzekki", "Nikita Lugovoy", "THUNDER THUNDER",
    "CanonicalTeamNames", "CanonicalTeamIds", "SubmissionIds", "EpisodeId",
):
    assert forbidden not in source
MAIN_PATH.write_bytes(raw)

with tarfile.open(ARCHIVE_PATH, "w:gz") as archive:
    archive.add(MAIN_PATH, arcname="main.py")
with tarfile.open(ARCHIVE_PATH, "r:gz") as archive:
    assert archive.getnames() == ["main.py"]

spec = importlib.util.spec_from_file_location("public_v27_agent", MAIN_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
assert len(module._LEGACY_ACTIONS) == 719
assert module._REBALANCE_ACTIONS is module._LEGACY_ACTIONS

import kaggle_environments
from kaggle_environments import make

notebook_engine_version = getattr(kaggle_environments, "__version__", "unknown")
env = make(
    "kaggriculture",
    configuration={"episodeSteps": 720, "seed": 270_810},
    debug=False,
)
schema_smoke = []
for seat, state in enumerate(env.reset()):
    observation = dict(state.observation)
    observation["player"] = seat
    action = module.agent(observation, env.configuration)
    assert set(action) == {"farmer", "hands", "market"}
    assert isinstance(action["farmer"], list)
    assert isinstance(action["hands"], list)
    assert isinstance(action["market"], list) and len(action["market"]) <= 10
    schema_smoke.append({
        "seat": seat,
        "farmer": action["farmer"],
        "hands": len(action["hands"]),
        "market_orders": len(action["market"]),
    })

print({
    "policy": "v27_midgame_meta_reset",
    "title_metric": TITLE_METRIC,
    "main_py": str(MAIN_PATH),
    "main_bytes": len(raw),
    "main_sha256": EXPECTED_MAIN_SHA256,
    "submission": str(ARCHIVE_PATH),
    "archive_members": ["main.py"],
    "research_engine_version": "1.32.6",
    "notebook_engine_version": notebook_engine_version,
    "research_exact_action_comparisons": 5760,
    "action_schema_smoke": schema_smoke,
    "ready": True,
})

