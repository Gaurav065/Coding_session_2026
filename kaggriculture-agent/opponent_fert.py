%%writefile main.py
"""Boatlee V16-RC2-MarketRelay for Kaggriculture.

A high-output production core with a guarded, debt-accounted,
three-turn FERTILIZER market relay for near-mirror farms.
"""
import base64
import copy
import json
import math
import zlib


_LEGACY_ACTIONS = json.loads(zlib.decompress(base64.b85decode(
    (
    'c-rk<O>Y}nlKd|^^I(#)Z0}8NbEbt+TZSwzG20Lt4a_VSSj--J_qN#ozOqEJij|R(k@;Rxvd1@CCad1}%Z!YS{Plm&{{8nq{_*!e'
    '&i>`svrm_wKcC$%&i>=~|N7g1Km6h0<3E1?<3IoYKM$XOJ^T6UcJuJR^uteI{`%YH$E#m1ug?}|?{Btei>3MV=bty5PiKqs{eOJk'
    'Y(6~vdHeI`^6qT$dh+LAHrF>FM}Piwd-LJT`@8WE?*DIb)QhY4fBEuh^!`JCem&c6KHohy^zdQV=h4p&?HhOBd&jO3$8Y&~b9?vm'
    '<3oo}_C33w()a9|sXqIsFIU$eetY=m-'
    'IuQuLLNN%rr!GN%lDhZAkiV(ee>%q96kTxKR(_aX4ZMnpT>)Vz2^9fM{|97x4HG6|Nb%<pr<e3aoP7^|I*QOcVA-TGTCJ4aYNG!Q'
    ')^!^JPs^-eM0SX4^Q(4M4m|d_|G?Ab^{K^Bb-'
    '2goQH*Hhodroqt^N3&@_LCQ_GG+%ls(=(lCG0xK!qG|64E|PaUW|Zdh;AKh>URhqudWVBK$84f}^|E;}v)Wi&dkfu|3N$00i>ybi'
    '*Z_WtJjdh`D7w?A!e@2;+|{_U}u_C877{)KA`HG@20f6JvB3f>wvG#H&^v-'
    'f+q=LA(YfBnGt@sl4vc|kupJ`+E0uD`l&qn+~Pkzo(e_-'
    'GgRDgWtUg~TV1Z~j|9Yf(GOj6ZZdG_b?V`{Y?O=|{`$FkFh2hJy1Swq0qVf0y7k#y>a16dv+>`=IkMfx*Y4RB7PU-cK!pk=ImswH'
    '@F>6NUjcEs)0-Oq(;nVFQ_GSvX3~5EY(r7$N&xb%ek}@c@-'
    '?i+`5iR<F9FJMS39Tu%P{`R?{|`_tz3_OEA)b@4KseCU2D_PQRQ=b~)AGWYK3Xr@|wBDrD<092N*RQ=wtjkCuZ9+76ZYI^-P-'
    '4np?qZe_H4j9-'
    'oJ3?R*5!M;|l8S{iERWLjhK9NLcPBH`Gd(mT#M%oJOt9&)wFid_KouJ~0o_`zz8??i^N=>XpvmJUXW}$m`s42J<u121KIst_+id*'
    'jqKoD@(qC8a<?X)~E-'
    ')~d<eDgh4ha(nJQM`dDo*m$#g>}0JK(kD{2Y^@yWEG?NgW@)jXiK1{m#emnrsK+o*!;yWkPh1+=fHtS&~9wl|Fy}SNHzpe)DJy*W'
    '7%E+@yQ|=WTSQx~DX~{#O~}paF6~HbU%z#qMcrDYY9M&ut+f2lE8x0wIU_c0+t>dxWsQqwKFlb+qF{*kc1k<E-'
    '|<+6u#cdAO3EKD2G3>0^7qIu0sw0;D_PinEwNiz}|8Xf4+w>t=mS6}aTY4`~Y17~;{1X5cwNg>@cOP>gl(nwMo9j2)6w*aghp2>n'
    'SPhv)*L<nO;k_<=z{4A<y2@WAuz4uG_fPEc&4ZU*QPq!SGNwleO_kV)7c_Az)Ngb(^~d-'
    'Ew+2gJS_Jjt7z>)lBWPVn{K{d>50KAgq2okbhatBD)B>KTOIKQVJ~=r$?$LJ!Y5EH?eg#Az8GYhba7QIOzed)^F4Hc2c{<*KwXqk'
    '=1db9=-'
    'PcnN)Z+%rqMX_OSR6hN~oq9BhyUgMRh#Zlx4&YJAfcRHi8HSV*3Au2h<(}Le5Kg|mCp!cdiU6+>XAQ4D!^UaUBY)WAMIiurr!yfs'
    'S)ipi*=?E+^-J-=%3zpaMWq}Tr9Q&r`XArN&n=`haI+Kj|uR>EJubr-hQv{ycS9%lG<eh-^9J~*%=#6S002-'
    'B9vtSAM#&g2tQCP?ToQv>A=3dlsSQ25?&O0=W9r#rCNSqjlcwyM6zs4TaGN+vTRG^eet^|Q_?Sm(?!@^1W(uFCtN4o|+_F!;-'
    'xcc+tONBSagg<2Cqp!CFp~1cYZx^qTN`#n!yo=ca({A?Zyu`C{1bc8~db&*u?5gyPDRYO);1R@t<q9HWhic_IR4d))m0X$OzP4l3'
    'l2YruZhU?p23EKDSN9##b5-{#<47tgWY`6=Ce$nrP>3Th7!3$nShYpL{T<Uv$Y+{)aR^?IG3o@`nnZfAX5-'
    'W>>J&W~ZarrdGWmH5Wfhplt~Z=}S1^l?wRN<l71|uI|AEOmyv>Zg>pRDbhs7sC8}cw2ETJ^<LbQd$b2eN=z_s&F1M1;sl0wNz<+C'
    '4Mtm7~o%6h7vPGIyAC!_~cb9zHB0zzzyiOf`Z7$VeQ9^>GgVi-@Y+Kc-'
    '<&jW}I^|k&_X!QSbb^VvGqkv;3%U9M9c+(n3X)^Iwjs?U`eC8iS*1iCsOZGaZkYr3%ffXQ`$2ohsJC^{p(cW~GHm$REBtovDo3R7'
    'Qr9c*moWS@5uW(8x%a)wxbqF-iK@qHbHZHxK5NbmX3%ame8loIvX@m{~h;mfYVF?vH42{JYzS%M^IV4=PO}#w41DI}PJ$BeAYzUB'
    '35iLP851rEExpy2aLBrlk3ftHS1jwZmgR@O=EpaEutFul2(R>&`n)yTha;D(2pMgD3-'
    'apa0nJGDJ5$NB{_u9E*470q5QM4|c=)yp0?CfI9HV9o9WyeC~Z#p<g;LOt<BpbU0Ar<zeF2sFD1WS8k(0HFx-'
    'kK+1kD{$>hY$`z*7`4U=xR8Y?V9!8`~-H#C~WMCwT-OC@X*|pV>eaq4q{<qm)pEUkibMm^)1poQsma=g~j~xo+jvkfV$i601MMe)'
    'd2*n3dXEj0Cr1&)<gYyQoLX$yc%fs2Nq9wG5|9eb(YT0WF#uu%&<>@aE;7o-'
    '%WLxP8nBXGRZ_a5^oklycrhGE*AwlK2Dy~CQeP+nJE{Z_2P3Q-n!ffg)9l=-'
    '5pAfNXU{Iv26NnR0Y&Jh?#<rNs{pYA%5va4<TftILAr<oUC&2wh*S0VL@<U9=3uHG~g~p%YHm#7w-'
    'CgcY^gzLWz@af`MWezBp2it2H`$xuxThF2?`&v<Ud@Rt{<bnD%+hLB9gHOoJwpih+#_QM<Qj@g#N$%8~>t0juO|Qf7f3ju!$RWcy'
    'TKnWDW=h&HFYk<h2?x5$)kgfo`81ax*kB`W*NEx|ZA9ciFPLgguOI}OR}3BHL0WC*@dXhci=JZ~VG@@pxF+cZLHs3{pRE!(o0Nvd'
    'IPCx8wZCV+0Ra-Rr}HUmYXJHDi(btyE8GIl4h65V;%9n@hR9J%o?fSykY^RaknIfI9-'
    'TRXS8WsCM2SXV_w)sO@%P4Obws7)fRFvZMF95?cb@J5Bx%w{*<M<Uh{Z+F|U;n(}zJDV6lIrik<s*O;HYUOqV<G-'
    '{C_e7|GC)tA6S(Eq=il0gg-r^7inQ2VLT?y<j3QH#fEN<P?V!Cxci!$VNL<FWjZ0jWB!)oVL?%uiGo?z8IW3wvx&?gw07A@#k-'
    '<Weu*)1t`NKD-aaXuve$em;R+woDka{p(kJI`<L72!%krRNTZ9R`=f(kmk%$&MA+H78FKPzbiq<?f@21hF{H9N<y%KI~y-'
    '?Iv6zXsR84cf1j`5E9&R)qG?xzpm_Zre#p!071g8B&ZUP9}yAvYGNeVyxjipC-'
    't%=GzB_h_Uj256cD~7%tC#LFz+H$wANpDTl!!jiHEF;Owl;9?l3tE_)pw3?<*!mb_M4AW#vk1MQE&B%28jUm9-'
    '(fmCTvPBdCUQMQ8Ka3URLqg_1Nj@!knhU*`HbbL-nl+I><INJF$V;wt;^O>Y?zxm043GHroOys~2&66JE?Z;{W;2t<{(CH&O|=RA'
    'fpZiTCh?z7(rmW}_I7;-+!3)#n*8+`B8_<6h3lhrquTJp^4@>@r?Bb_$irf{TwI(?wIO-'
    'T5(fj0t0^o|y{M%~nk8x5;01sNnQB_^a*f#zY#3A}D*U1m%sm36RTk&)0=NAhr+-'
    'Vt(T7(cXzIEcB{JgR72lZt7|T%82@H4|$Et?>E+SEc<<!zs;E&(T?23$o@Cedq!qlz*B8P*7J>*CMs5nJvu&qq#(ViiQ(X!+hEE)'
    '*i8*VCRx-EP<_-0@g*w>{JoF)AMRy6q9$Hk8cuMj(w{23v!#ZMEnl^6Y#Jbvg!SpWuM|b?&E>66Qltq0CS-'
    'r%NB%(WUAJ4)oZbhW<0Jo2W#D4(6^Z6zKt`cYwSy|rJVfV(#{xXm`B0LMK+?J7$jwbuq;l+iav$xncW$&^F?GKg6vDJ&8XaqhvWN'
    '^1`uD=m0UB99AfTmbSmQv7CYaPOsS;*Q1FT#{(eB-#L3F`#4s0&(y+;^6Fit~Pq=5nH_6@+R82HD5&LBdaN^kmz-4?Jo1-'
    'b2KSUSy)QVC*0wXy48v#VLa#L4#C=qd3-WfJL$oZ<(MiObDD1zCP{VEMtTc+;ms?E&hi@y6l__DU-%~DrCsqkv!7~i^-'
    'bn5VE)48V_eYS`2S%Vi%LxGOhJePwi%OV5MDa-H$!L~V^>QvSi4_f9O9ff!y-'
    'M6JQ!G=*y?wm|%4`^%!i=kyR*#&^Zyp*1bEtwuNZd`Xpa@R9q0-'
    '2W>@JJ5>4NYeI$0F@jp&SM|?*P2WfILj+jf4QHY!^5L8v$4(L8MAo36(30Mc64P80*5J#<Z_$I#4uXUE)=0)w}Qj97JMx`64xi^T'
    'N>Ep6F;Os2Q6B6ezN(oz!Tg{&y~kcN0#Q3T?F%*-A-'
    'GxN(rC6m=@~b68n~SL``ugh2Tg5Ge5iTP3uLteb3OAx)04UEC7QRbY<I<*SaPq|0*~COs~kG|bI66*<jIn2$ZpnyZ@%$M)f~LJxQ'
    'C{!gfp4uADps482qH6k}Xb;$WQTv1;<5fV<Y#{}p9B?OMOGFLqA$$C?%AXE=9C&VfB6jv=6$CKI8-XJpw$Gq<dFb`;YQ7Er-'
    '4KJzOyv8bKS#Ui5lF(d{s!t2C4(c4B_#t+1DyTv$Q9nwuro|N4c_3t@)gS;zqgRfW<2C7SG)8c!sL)6$duWGdYdj>5x>hWPBE4d='
    'aafa}tzsIY&zT8O!unZ-fk<3B&SYl7V@;udEnl6T#DxU~0B=0F;JVUT0+c1yjU*yeGmbd~2yIf%BVFt%DkW=o3s@{7Lp{gXKteo#'
    'o1R`|OlXU2e?c;Xi7#%IYS3=1D3~QlJ1mw=+s~d%MGR}0v=`4N7!ROaDRdH{e#t58aSt_6qEk96%}rFoACb4!Qd9}=QwaR!NP<t0'
    'uy;;!!MB%*Jq5jHMz>nj!{w}lPN}rnYSo?}Q_QGU1fT-'
    'vWxIJk(PSVfB#`^IV!*ymAPw-1(A@2zOx;CCK$mPnOR2459N_)B#vElhk%Zk-Ezm8c98lM}fv6)z8HI%@(by9_GDb&WCydB4>sys'
    'Ol3<EmJqoZ@28-'
    'G8KG4Ujy_ZNND!+zu5(=seia!Y68BP_sG++l~AcQUTKmwA{aAq1aVrL|lxjIyu44E}gdCm=n=B;Be@+~{~>Ji(O9HA2|B)u<LV`N'
    '&HZ#S`_E21~7#Z+R>*EUx~@rq-'
    '}G7Myy^9&KpHU=UO3SEPLzbBbvWhpf8zK1OMML#EYZk2CVyxtHoDyrF#P~E~4+iv<0CK|=7vN&;fdWXI0bJE>}a9X5qtUGx?phL2'
    'xcP_S2p>-'
    '5<K_f&|%(^Va3A1YYI8Q)vpn0*Mt_u5(S}@D}&E=!Fr1j@@_wzh|V0g#1)8}AeG57>boGMr~lM+Ao1X2Qt$=F{PWktN~1)rXuCZ)'
    '1cj3-'
    'ZJuq|rIf{URTYC9H3)!b8R<Ylr=g)79SPf#cql0BLM3k0NSy7OqCNi~&@)dv<0I38cb@lipE8pIcC9cw5`Ae;w?>)h0`Kx)Ez>5P'
    'Oc4p_r{D+=4JL`Epgof0djwcV8JaqTF?T*`-VDwV?S1#SR<6qYrm^CwkvPr&aezpSll_cxJ-GD}3>7t|}|pU{)d&Ejy9N^%kGIm&'
    '}8&`e6WVMd++z(CTRS*f|tsRU2Ul4ivqfT_fOF&phbmzYCywlBp?F$<n2-_A~eS-'
    'L`!iJneFvh0xyyB`%L(YGjGC}pKMn5yEmFvW=a95yK+a$*Flu%*?Yucc*&J|Y?9e301}whP3DLKXp)3(QrD!(mDxtpJ~t#q#g;ND'
    '5Cqq6f*rt^MAQ9cikPBaBuqV~gg;kqou=(FgK5#B2!ka`L&2717ShJxNYvayHSzwcE@VV2F`6cpC-'
    'A6^qLWX*g9KRcZcpvxa8X1pKAiyab`nB6kd!&(cUK_j_h~1avyA*Ggk*Qn({E3G6OSZEIQ+qygg2Y3E8eEGL}OObu3A(1K7xYRa1'
    'eXcPOB;oh;ls+?|Te8uOKLHp;VJb`SA&PqKq<w&IEi172OAHC;gq^2~Ax13*`D8HpkF%1r#y)J6C%n=XGSKnZs5({uwDl}WZWTHa'
    '2c6H{<KJ-W)(4BeWG!BeSr9yVZTA|;ZRmDZmhKz&C8JAfttSyNi4k!EO`sO1@8Qm)6zQB-'
    '6bDuPWtE<Ed$)}FDDAYEjl_n~Dg4Dc8nlQjWw|E@W1W?>T$Luap^Ugb=`iRHWD!&B&G{ig22!gdi47c4JFNK=1>?(`F!VqqRO1}O'
    '{6^pkein;igvv)~C=4=dxOr}IGr08u$twN2jVo3sqB9g(5qTW4nunZ#B20B5PqXKp`)IZ9J9Vt1yF_Gvn`MH(KIo?XnOE}dLzh7H'
    'zlBq|vUFD?Cpg+@=aJrobP4i^eAn2Qv$csG?uws+sQTTOcg^~7RW3awJh2$}yw@a>E$S3zhD}nS9_e3)i_Dp#>QJtGze{#(L3+iq'
    '2fzsffCfYtCFrPyzQ|IA+sjco4rLzZv!6(1zQG0j_`5>Z5k@F5l)-'
    'TTMv)vDK6OX<iC=VgneA*ufz^!U9=fU81sDNA>e2j5_N9@3^+SE?s<51lRR&SWE3e!rhb*R`!u$>&9>qYD9gNEoOoA@_lT3@GfPK'
    '>d}3pi0JPttw@GL|<<tE3F=DUA9hWT5f4AIUE-pkkDu(;H`>Fr2iZz7)5*5~+jyLAAn3r9A1NAsb0Ynni4ivQXStQ#v$!dr#|Pu7'
    'nFS1P)8H-'
    'gV&3;GyMKSCt?s<wvW!CqC=e@{aLJG6z!Vru_8f>iWZP4|dYs7oVgiCbf|cARUMH0|#X}U0=T6>};vDu9tOTKnM17q2)PFEM?<)>'
    '|V)E9&!)Ez<2-*lUa(G>yt7xft9<AtQ4LYjsBNIPn8Pr%S2cqaOtBW0b)h8gf>(n@dlobhxHzXf&k>R-v-'
    '2DGI;?(*N(i*SFzy>*M(ok4?FVYDu{~>&dMXeYwIv)An!4f=F65k=as*fpfXjC3`z}gPj-vznRO`|7661%oeB#M*>-'
    'v@?~{~jvrY9hAdb8xJ5VbjmloSvpIeY`x%v*scTF_8b^oN(6ynjydE=N-'
    'oH*g*OPxxM5&57bsMJLcra(|*1;rxDSwVfL&NtJGQtQ&#eo{)x;bSF8!<z4cPDN=Kag$k5yOQ9Rwv7Y^%nwNh6<A0fTDLT5<^}5#'
    '=1O&*26-'
    '+yWmC##N>oT~tFEjeqS?|do;Q$dNTt|hP!CDcj?L8gAz6n(14zZL%K8K2mtTPS>_fH+64eBGS}<LQEX$K%8I_y<>9C7*-'
    'x7E`Eo&yHHyt^L%M$qrUyg!?yXgAnwihCE8C55GQxR9NVgBVa9_vxbRU!f3A{f*13TARnit`DS&BMx8{({VEN^5f6r8SsxEkQd@Q'
    'MlaGy8b7~e4EKZe_eIZ;nObE^4u|9{-'
    'kA|n2|^R(#i3+#+6tUN+J<ZMn4~xZ>F%6TDUW!1<q583Jte@H&Pq{ea*yaPglK)4td@>S1n@3p-%X`5uHGhX`><dkd-'
    'R&*{c+S;+9M$Nn&oq#$^{o201vq!f<}TP3==5833_~VWI)WcD50qD+tiSR+4{DmVYMHrLMJyB_F@Q>enl37=*Bb@rGe>dcG(*Tk<'
    '}$>!K!NMI}`%5sZSLh7v=Q*#zoPehu0w6PBP{K03wPqBb7CS4tjYLbiPiQh!q7{y6w97EV{smqk5%L{18t(hF8DVy}Q7kYmLcZJ('
    ';dlqXpM@s+rXX0);6sCWw5^Z^T?0E~5%Fq}M6qoS24ze<si*wOnI)hiPKU;=PUB4IWSE8507PQ~Qq1wxob?bvxra-'
    '^6t@AOMW*p1P_f{~?CSJXN3fV~v8H>d8U>uUuMVh15-'
    '_~miOl|4+KWVpT;<guxOo)0gsixu@~>Tj<EGBF#>BLImqQFCXEQI9|~8kzi8PnblidQZQtsTZ9%VFVMHqFkzIE=9g}B2R=ZhUnUt'
    'G_R;8bQ-A93hr^tk#G(cTA{7BN_$+pTlpLntuFAR!UgGD^ch93t&kC-oiXX?0x<WON=}HlZF(r<N@`BAzOq`!kcscMBrKwh#L^-'
    'nLsiTbXkq=KPyR{{Rg|+z)iU2t^fAL^#NN3k(^Tu&NeiK(A*)BL)9H#+2Vx#M-%`Om0YI7Igaw%}W8?YVeL_)R!q;l-'
    'N{GZxJhWnoca*Ma1ZybB%Xe$4S%GG})G$Si%d7K}6jed%&Hx{Wd9o>Z)DB`|m{0Q5OHZ~1$Wx!YnO%uu3!<Ej9TdRyBGW{A&YNB='
    'G$^%~VZ%KMR%r6pORmE+D(Lqt*vHK3;*ApG=bl)f!n9hKD-!kQQHioTwCGw>V<q;5$eR*d>0a=sBt)?kDow>)r9_G5-'
    '%?lF*$N^pIwdNuu^1sJed$k}k)!9qGFFTf@$3N6RWeVI=vQR)s7fjQp*zND;jAUGN?bppSw2}&AlbQ-'
    'N3%#uRi?5jR;)l4Zwi~QTo_K+0CC+LMS)y#5b8S{Vy1NM=c?VQXI|@eCMgqgVL|4oGXjyXkJ^K=#uH`}u>wE)5%-'
    '}IJCHE7K*S=@X(k&yhuzRsPH;bwLdGiA6_V5v^eT!)$~6T85=!fag$GYSY0Z{)Ru~%$%E}`y^;3vZi6r?ls+yNWXN(|6BXJ0{HWH'
    '|z{c>je_;oc#N>;;1X4Q0Q-FzQrK!z>=GW5zIL$ALlIp&upibGj3lz-YqCPyX7NG0DGlja#@bF`r~l*d!ZvuP?il0_xeOn%||IyC'
    '=_g$V_E=0->jqS>Ev)SFCKYgAq^v{(X082$#l;r@YoALGn1cn!+d06Lvm$fufel}!{_)|FLQ2wZk&Xw7z!+*j-tRrO$<3nf-'
    '7d@@B5NGVt)Y6PiT&y7h#O0`ndtoWj`YFxaCNiy;rxp;ZdRiaC>wI7P2D595=lsGK+O{&TTuKuy%l-mQj6fz-'
    '~g~cQohASfcK`xe2wk>A9M&^+pxM7R~UK1)21YoQmg4NQHCOnlC!cuEH!&}>U2=;JQ>O58HO5`OuZ3H57bWAPEA3KD;Bxo5$cnpG'
    'QoZjW{1~&FNJt^hG^x0hnlvY?k35>#Pkn;2$fICfzPUragkn)<=30arM#3mt_$@wlK=o5R?Bt=5@C@Lkf+SH7e<$Qy5Wh`C%xJyU'
    '4?4$skX#z!5WTIQeCn*=GUM`s4ueltY^fr)$(jxQ~_!eaW?ZOU->L}^7ZmI5#4owm`Ox(2;b!TO9I)=3Ut*NS^ZD(A-DRF_6>P-'
    'Z(wr1n-VnJkMA~%VIJ9-'
    'f@BuqIb@#t%z0uKr$zI7H!o7#8qBF?F0QGlX;y|spI_9&n#ZpnF1Br8Q1=xuDXXEKJvGH6VV(Nm3ys=&OfR)O*O09K#Z79vxV!B{'
    '`^=CK;xOvo$L*<d&9MZ&Xp%TW&^E+IH&d(;S=)TBsQ7Ll^O#%}m|XO~z?bs~*yg%tod<oq?w8ZsgwFEg9S!$rzXi>wb=Xc2||(9s'
    'iAX`~621z<jwEMT6kqEOsl&6Kk#`HkZ{EPd*yP)}TqF{xZ_PF~d;oh(45XEN~Bl_K0FgbVfbbLJDo%a^IpDssR<ibjG;O*!h67R4'
    'N}z7wc$ymG!J_klLE%4D*Y6RTX+97ru4Q_1lv`HZ$f!1RPdjB=e=QrfprDpC=-'
    '*rqDk)Qa>r+<+9A&{9Wv8RRs{7(O{H3B1uXA2LIiYZxavw3Q=cp+yoyCI!U(sybvFyj8b>;*5eC!dihJURB4bOl`dky~+ISfhYj0'
    'd=p>$DbJ)SqWq%~LL;Wv60?P0Q}?w|b^`i}xeD>bY^3oY-Ubyw)wIBfO;f2#$i>E3L*ik}#@wlS$Gu)=fyTo^E1w6v?NnNI+xUo<'
    'q$q)yk&2_~=<55p5t2jvX%OC7!J^((WO!EVG(_2@lsD?14fREoNNtVUo@kWyOa<>z(0Wz#15!;B0%`mtmrm8<#;cGlRr+Ug<d~{n'
    'Fc^%TQ49UTWgq#9kqbqCLw}rFaOmU_6bazBbYL1d=2WGC73?_pD;gvnM>BTd{Kb8((VV3hq9iDT@v(=MPMoLu07eqHh2+EZ+Z3k0'
    '5IC&6#Q3*DHxkW)POe)fm3Cs4>4aTlrt<Amv#5im^r5X+>kC!-v2XbU*vq)NZys88|NntQ0?7'
    )
)).decode("utf-8"))
_REBALANCE_ACTIONS = _LEGACY_ACTIONS
_PRICE_FLOOR = 1
_DEMAND_ALPHA = 0.25
_MARKET_PARAMS = {
    "WHEAT": (25, 10000, 400, "sqrt", 0.8, "log", 0.2),
    "CARROT": (35, 10000, 450, "log", 0.2, "sqrt", 0.7),
    "TOMATO": (60, 10000, 200, "linear", 0.4, "sqrt", 0.6),
    "STRAWBERRY": (120, 10000, 100, "sqrt", 0.7, "linear", 1.6),
    "MELON": (250, 10000, 300, "log", 0.2, "sq", 3.6),
    "EGG": (50, 10000, 332, "linear", 0.4, "log", 0.2),
    "MILK": (160, 10000, 122, "sqrt", 0.6, "linear", 1.6),
    "WOOL": (200, 10000, 105, "log", 0.2, "sq", 3.2),
    "FERTILIZER": (100, 10000, 200, "linear", 0.4, "linear", 0.4),
}
_SHOP_PRODUCTS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}
_WEED_STATE = {0: {}, 1: {}}
_WEED_REPLAY_STEPS = 8


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(value, key, default)


def _regime(configuration):
    interval = int(_get(configuration, "townCenterSellInterval", 12) or 12)
    return "rebalance" if interval >= 24 else "legacy"


def _copy_action(action):
    action = copy.deepcopy(action or {})
    return {
        "farmer": list(action.get("farmer") or ["PASS"]),
        "hands": [list(order or ["PASS"]) for order in (action.get("hands") or [])],
        "market": [list(order) for order in (action.get("market") or [])],
    }


def _seat(obs):
    return 1 if int(_get(obs, "player", 0) or 0) == 1 else 0


def _farm(obs, seat):
    farms = list(_get(obs, "farms", []) or [])
    return farms[seat] if seat < len(farms) else {}


def _align_hands(action, obs):
    action = _copy_action(action)
    expected = len(_get(_farm(obs, _seat(obs)), "hands", []) or [])
    hands = list(action.get("hands") or [])
    if len(hands) < expected:
        hands.extend([["PASS"] for _ in range(expected - len(hands))])
    action["hands"] = [list(order or ["PASS"]) for order in hands[:expected]]
    return action


def _tile_at(farm, position):
    try:
        x, y = int(position[0]), int(position[1])
        return (_get(farm, "tiles", []) or [])[y][x]
    except (IndexError, TypeError, ValueError):
        return "LOCKED"


def _trace_actor_action(actions, step, actor):
    trace = actions[min(max(int(step), 0), len(actions) - 1)] or {}
    if actor == "farmer":
        return list(trace.get("farmer") or ["PASS"])
    hands = trace.get("hands", []) or []
    return list(hands[actor] if actor < len(hands) else ["PASS"])


def _weed_repair_action(obs, action, actions, step):
    action = _align_hands(action, obs)
    seat = _seat(obs)
    game = _WEED_STATE[seat]
    if step == 0 or step < game.get("last_step", -1):
        game = {"last_step": step, "active": {}}
        _WEED_STATE[seat] = game
    game["last_step"] = step
    farm = _farm(obs, seat)
    positions = [_get(farm, "farmer"), *list(_get(farm, "hands", []) or [])]
    unit_actions = [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]
    active = game["active"]

    for actor, transaction in list(active.items()):
        index = 0 if actor == "farmer" else int(actor) + 1
        if index >= len(unit_actions):
            active.pop(actor, None)
            continue
        age = step - transaction["start"]
        if age == 1:
            unit_actions[index] = list(transaction["intended"])
        elif 2 <= age <= 1 + _WEED_REPLAY_STEPS:
            unit_actions[index] = _trace_actor_action(actions, step - 1, actor)
        else:
            active.pop(actor, None)

    for index, (position, intended) in enumerate(zip(positions, unit_actions)):
        actor = "farmer" if index == 0 else index - 1
        if actor in active or not isinstance(intended, list) or not intended:
            continue
        if intended[0] not in ("BUILD_PASTURE", "PLANT"):
            continue
        tile = _tile_at(farm, position)
        if not isinstance(tile, dict) or tile.get("kind") != "WEED":
            continue
        active[actor] = {"start": step, "intended": list(intended)}
        unit_actions[index] = ["DIG"]

    action["farmer"] = unit_actions[0] if unit_actions else ["PASS"]
    action["hands"] = unit_actions[1:]
    return _align_hands(action, obs)


def _shape(name, value):
    value = max(0.0, float(value))
    if name == "linear":
        return value
    if name == "sq":
        return value * value
    if name == "sqrt":
        return math.sqrt(value)
    if name == "log":
        return math.log1p(value)
    if name == "log10":
        return math.log10(1.0 + value)
    raise ValueError(name)


def _market_price(item, inventory):
    base, equilibrium, scale, below_func, below_target, above_func, above_target = (
        _MARKET_PARAMS[item]
    )
    if inventory < equilibrium:
        amplitude = below_target * base / _shape(below_func, scale)
        price = base + amplitude * _shape(below_func, equilibrium - inventory)
    else:
        amplitude = above_target * base / _shape(above_func, scale)
        price = base - amplitude * _shape(above_func, inventory - equilibrium)
    return max(_PRICE_FLOOR, int(round(price)))


def _is_sell(order):
    return (
        isinstance(order, (list, tuple))
        and len(order) >= 3
        and order[0] == "SELL"
        and order[1] in _MARKET_PARAMS
    )


def _impact_score(obs, order):
    if not _is_sell(order):
        return float("-inf")
    item = str(order[1])
    try:
        quantity = max(0, int(order[2]))
    except (TypeError, ValueError):
        return 0.0
    market = _get(obs, "market", {}) or {}
    inventory = _get(market, "inventory", {}) or {}
    prices = _get(market, "prices", {}) or {}
    current_inventory = int(_get(inventory, item, 10000) or 0)
    current_quote = float(
        _get(prices, item, _market_price(item, current_inventory)) or 0
    )
    later_quote = float(_market_price(item, current_inventory + quantity))
    return float(quantity) * max(0.0, current_quote - later_quote)


def _demand_per_day(obs, configuration, item):
    town = _get(obs, "town", {}) or {}
    shops = list(_get(town, "unlocked_shops", []) or [])
    turns_per_day = int(_get(configuration, "turnsPerDay", 24) or 24)
    shop_interval = max(
        1, int(_get(configuration, "townShopSellInterval", 4) or 4)
    )
    demand = 0.0
    for shop in shops:
        products = _SHOP_PRODUCTS.get(shop, ())
        if item in products:
            demand += (turns_per_day / shop_interval) * (
                2 if len(products) == 1 else 1
            )
    regime = _regime(configuration)
    if item != "FERTILIZER":
        center_default = 24 if regime == "rebalance" else 12
        center_interval = max(
            1,
            int(
                _get(configuration, "townCenterSellInterval", center_default)
                or center_default
            ),
        )
        day = int(_get(obs, "day", int(_get(obs, "step", 0) or 0) // 24) or 0)
        multiplier = (
            1
            if regime == "rebalance"
            else (4 if day >= 20 else 2 if day >= 10 else 1)
        )
        demand += (turns_per_day / center_interval) * multiplier
    return demand


def _order_score(obs, configuration, order):
    score = _impact_score(obs, order)
    if _regime(configuration) != "rebalance" or score <= 0 or not _is_sell(order):
        return score
    item = str(order[1])
    quantity = max(0, int(order[2]))
    market = _get(obs, "market", {}) or {}
    inventory = _get(market, "inventory", {}) or {}
    current_inventory = int(_get(inventory, item, 10000) or 0)
    demand = max(0.25, _demand_per_day(obs, configuration, item))
    excess = max(0.0, current_inventory + quantity - 10000)
    urgency = min(1.0, (excess / demand) / 10.0)
    return score * (1.0 + _DEMAND_ALPHA * urgency)


def _rank_sell_slots(obs, action, configuration):
    action = _copy_action(action)
    market = list(action.get("market") or [])
    rows = [
        (_order_score(obs, configuration, order), -index, list(order))
        for index, order in enumerate(market)
        if _is_sell(order)
    ]
    if len(rows) < 2:
        return action
    rows.sort(reverse=True)
    ranked = iter(row[2] for row in rows)
    action["market"] = [next(ranked) if _is_sell(order) else order for order in market]
    return action



# Boatlee V16-R5B: weed-replay-safe livestock-mix controller.
_V16_NAME = 'Boatlee V16-RC2-MarketRelay'
_V16_SWITCH_STEP = 161
_V16_PURCHASE_STEPS = frozenset([192])
_V16_ACTOR_WINDOWS = [(4, 193, 212)]
_V16_ROUTE_STATE = {0: {"last_step": -1, "yarn": None}, 1: {"last_step": -1, "yarn": None}}


def _v16_yarn_route(obs, step):
    seat = _seat(obs)
    state = _V16_ROUTE_STATE[seat]
    if step == 0 or step < int(state.get("last_step", -1)):
        state = {"last_step": step, "yarn": None}
        _V16_ROUTE_STATE[seat] = state
    state["last_step"] = step
    if step < _V16_SWITCH_STEP:
        return False
    if state.get("yarn") is None:
        town = _get(obs, "town", {}) or {}
        shops = tuple(_get(town, "unlocked_shops", []) or [])
        blocked = {"SMOOTHIE_SHOP", "PIZZA_SHOP"}
        state["yarn"] = (
            "YARN_STORE" in shops
            and not any(shop in blocked for shop in shops)
        )
    return bool(state["yarn"])


def _v16_swap_cow(order):
    order = list(order or ["PASS"])
    if len(order) >= 2 and order[1] == "COW":
        order[1] = "SHEEP"
    return order


def _v16_convert_livestock(action, obs, step):
    action = _copy_action(action)
    if not _v16_yarn_route(obs, step):
        return action
    if step in _V16_PURCHASE_STEPS:
        action["market"] = [_v16_swap_cow(order) for order in (action.get("market") or [])]
    hands = [list(order or ["PASS"]) for order in (action.get("hands") or [])]
    for actor, start, end in _V16_ACTOR_WINDOWS:
        if int(start) <= step <= int(end) and int(actor) < len(hands):
            hands[int(actor)] = _v16_swap_cow(hands[int(actor)])
    action["hands"] = hands
    return action



# Boatlee V16-R6: inventory- and price-aware WOOL release for YARN_STORE.
_V16_WOOL_GATES = ((480, 170), (600, 120), (672, 80), (719, 1))
_V16_WOOL_PRESSURE = 78
_V16_WOOL_BATCH = 16
_V16_WOOL_GAP = 6
_V16_WOOL_STATE = {0: {"last_step": -1, "last_sale": -1000}, 1: {"last_step": -1, "last_sale": -1000}}


def _v16_wool_gate(step):
    for end_step, gate in _V16_WOOL_GATES:
        if step < int(end_step):
            return int(gate)
    return 1


def _v16_wool_controller(action, obs, step):
    action = _copy_action(action)
    if not _v16_yarn_route(obs, step):
        return action
    seat = _seat(obs)
    state = _V16_WOOL_STATE[seat]
    if step == 0 or step < int(state.get("last_step", -1)):
        state = {"last_step": step, "last_sale": -1000}
        _V16_WOOL_STATE[seat] = state
    state["last_step"] = step
    market_orders = [list(order) for order in (action.get("market") or [])]
    if any(len(order) >= 2 and order[0] == "SELL" and order[1] == "WOOL" for order in market_orders):
        return action
    private = _get(obs, "private", {}) or {}
    shed = _get(private, "shed", {}) or {}
    wool = max(0, int(_get(shed, "WOOL", 0) or 0))
    if wool <= 0 or len(market_orders) >= 10:
        return action
    total = sum(max(0, int(value or 0)) for value in shed.values())
    market = _get(obs, "market", {}) or {}
    prices = _get(market, "prices", {}) or {}
    price = max(0, int(_get(prices, "WOOL", 0) or 0))
    terminal = step >= 713
    pressure = total >= _V16_WOOL_PRESSURE
    price_ok = price >= _v16_wool_gate(step)
    gap_ok = step - int(state.get("last_sale", -1000)) >= _V16_WOOL_GAP
    if not terminal and not pressure and (not price_ok or not gap_ok):
        return action
    quantity = wool if terminal else min(wool, _V16_WOOL_BATCH)
    if pressure:
        quantity = min(wool, max(quantity, total - (_V16_WOOL_PRESSURE - 12)))
    market_orders.append(["SELL", "WOOL", max(1, int(quantity))])
    action["market"] = market_orders[:10]
    state["last_sale"] = step
    return action


def _v16_agent_impl(obs, configuration=None):
    try:
        actions = (
            _REBALANCE_ACTIONS
            if _regime(configuration) == "rebalance"
            else _LEGACY_ACTIONS
        )
        step = min(max(0, int(_get(obs, "step", 0) or 0)), len(actions) - 1)
        action = _weed_repair_action(
            obs, _copy_action(actions[step]), actions, step
        )
        action = _v16_convert_livestock(action, obs, step)
        action = _v16_wool_controller(action, obs, step)
        return _align_hands(_rank_sell_slots(obs, action, configuration), obs)
    except Exception:
        farm = _farm(obs, _seat(obs))
        return {
            "farmer": ["PASS"],
            "hands": [["PASS"] for _ in (_get(farm, "hands", []) or [])],
            "market": [],
        }


# Current official Kaggriculture defaults used by the audited two-argument route.
_V16_OFFICIAL_CONFIGURATION = {
    'turnsPerDay': 24,
    'townShopSellInterval': 4,
    'townCenterSellInterval': 24,
}

# Boatlee V16-RC2: guarded, debt-accounted inter-turn FERTILIZER relay.
_RC2_ROUTE_CHECKPOINTS = (216, 240, 264)
_RC2_ROUTE_DISTANCE_MAX = 8
_RC2_RELAY_LEAD = 3
_RC2_RELAY_FIRST = 278
_RC2_RELAY_LAST = 662
_RC2_ROUTE_STATE = {
    0: {"last_step": -1, "checks": {}, "locked": False, "due_step": -1, "due": 0},
    1: {"last_step": -1, "checks": {}, "locked": False, "due_step": -1, "due": 0},
}


def _rc2_public_signature(farm):
    counts = {
        key: 0 for key in (
            "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
            "COW", "SHEEP", "GOOSE", "PASTURE", "COOP", "WEED",
        )
    }
    for row in (_get(farm, "tiles", []) or []):
        for tile in row if isinstance(row, list) else [row]:
            if not isinstance(tile, dict):
                continue
            for field in ("crop", "animal", "kind"):
                value = str(tile.get(field, "")).upper()
                if value in counts:
                    counts[value] += 1
                    break
    return (
        len(_get(farm, "hands", []) or []),
        len(_get(farm, "unlocked_quadrants", []) or []),
        tuple(counts[key] for key in sorted(counts)),
    )


def _rc2_route_distance(obs):
    farms = list(_get(obs, "farms", []) or [])
    if len(farms) < 2:
        return 10**9
    left = _rc2_public_signature(farms[0])
    right = _rc2_public_signature(farms[1])
    return (
        abs(left[0] - right[0])
        + 3 * abs(left[1] - right[1])
        + sum(abs(a - b) for a, b in zip(left[2], right[2]))
    )


def _rc2_state(obs, step):
    seat = _seat(obs)
    state = _RC2_ROUTE_STATE[seat]
    if step == 0 or step < int(state.get("last_step", -1)):
        state = {
            "last_step": step,
            "checks": {},
            "locked": False,
            "due_step": -1,
            "due": 0,
        }
        _RC2_ROUTE_STATE[seat] = state
    state["last_step"] = step
    if step in _RC2_ROUTE_CHECKPOINTS and step not in state["checks"]:
        state["checks"][step] = _rc2_route_distance(obs) <= _RC2_ROUTE_DISTANCE_MAX
        if all(checkpoint in state["checks"] for checkpoint in _RC2_ROUTE_CHECKPOINTS):
            state["locked"] = all(state["checks"].values())
    return state


def _rc2_future_fertilizer_quantity(step):
    future_step = step + _RC2_RELAY_LEAD
    if not (
        _RC2_RELAY_FIRST <= step <= _RC2_RELAY_LAST
        and 281 <= future_step <= 665
        and future_step % 24 == 17
        and future_step < len(_REBALANCE_ACTIONS)
    ):
        return 0
    return sum(
        max(0, int(order[2]))
        for order in (_REBALANCE_ACTIONS[future_step].get("market") or [])
        if len(order) >= 3 and order[0] == "SELL" and order[1] == "FERTILIZER"
    )


def _rc2_repay(action, state, step):
    due_step = int(state.get("due_step", -1))
    if due_step != step:
        if due_step >= 0 and due_step < step:
            state["due_step"], state["due"] = -1, 0
        return action
    remaining_due = max(0, int(state.get("due", 0)))
    market = []
    for raw in (action.get("market") or []):
        order = list(raw)
        if (
            remaining_due > 0
            and len(order) >= 3
            and order[0] == "SELL"
            and order[1] == "FERTILIZER"
        ):
            requested = max(0, int(order[2]))
            reduction = min(requested, remaining_due)
            requested -= reduction
            remaining_due -= reduction
            if requested <= 0:
                continue
            order[2] = requested
        market.append(order)
    action["market"] = market
    state["due_step"], state["due"] = -1, 0
    return action


def _rc2_market_relay(obs, action, step, configuration):
    action = _copy_action(action)
    state = _rc2_state(obs, step)
    action = _rc2_repay(action, state, step)
    if not state.get("locked") or state.get("due", 0):
        return action
    target = _rc2_future_fertilizer_quantity(step)
    if target <= 0:
        return action
    market = [list(order) for order in (action.get("market") or [])]
    if len(market) >= 10:
        return action
    private = _get(obs, "private", {}) or {}
    shed = _get(private, "shed", {}) or {}
    available = max(0, int(_get(shed, "FERTILIZER", 0) or 0))
    for order in market:
        if len(order) >= 3 and order[0] == "SELL" and order[1] == "FERTILIZER":
            available = max(0, available - max(0, int(order[2])))
    quantity = min(target, available)
    if quantity <= 0:
        return action
    market.append(["SELL", "FERTILIZER", quantity])
    action["market"] = market[:10]
    state["due_step"] = step + _RC2_RELAY_LEAD
    state["due"] = quantity
    return _rank_sell_slots(obs, action, configuration)


def agent(obs):
    try:
        configuration = _V16_OFFICIAL_CONFIGURATION
        step = min(max(0, int(_get(obs, "step", 0) or 0)), len(_REBALANCE_ACTIONS) - 1)
        action = _v16_agent_impl(obs, configuration)
        action = _rc2_market_relay(obs, action, step, configuration)
        return _align_hands(action, obs)
    except Exception:
        farm = _farm(obs, _seat(obs))
        return {
            "farmer": ["PASS"],
            "hands": [["PASS"] for _ in (_get(farm, "hands", []) or [])],
            "market": [],
        }
