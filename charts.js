export const C={bg:'#0a0e14',text:'#ffffff',muted:'#d0cfc6',faint:'#9a988f',grid:'#24303d',coral:'#fb8d94',soft:'#51343e',mint:'#96cbb7',gold:'#e8c28d',purple:'#b7a5db',neutral:'#8a93a0',panel:'#101722'};
export const W=880,H=490;
export const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
export const num=(n,d=1)=>Number(n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
export const signed=(n,d=2)=>(n>0?'+':n<0?'−':'')+num(Math.abs(n),d);
export const text=(x,y,s,size=20,fill=C.text,extra='')=>`<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" ${extra}>${esc(s)}</text>`;
export const rect=(x,y,w,h,fill,r=0,extra='')=>`<rect x="${x}" y="${y}" width="${Math.max(0,w)}" height="${Math.max(0,h)}" rx="${r}" fill="${fill}" ${extra}/>`;
export const line=(x,y,x2,y2,color=C.grid,extra='')=>`<line x1="${x}" y1="${y}" x2="${x2}" y2="${y2}" stroke="${color}" ${extra}/>`;
export const circle=(x,y,r,fill,extra='')=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" ${extra}/>`;
export const tip=(content,body)=>`<g tabindex="0" role="img" aria-label="${esc(content)}" data-tip="${esc(content)}">${body}<title>${esc(content)}</title></g>`;
export const lines=(x,y,ss,size=18,fill=C.muted,gap=29,extra='')=>ss.map((s,i)=>text(x,y+i*gap,s,size,fill,extra)).join('');
export const pill=(x,y,label,color=C.coral)=>rect(x,y-22,label.length*10+28,31,C.panel,6)+text(x+14,y,label,14,color);
export function svg(body,label){return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>${body}</svg>`;}
const centered='text-anchor="middle"';
const end='text-anchor="end"';
const bold='font-weight="600"';

export function opening(rate){
 let b='';
 b+=circle(330,226,177,'none',`stroke="${C.grid}" stroke-width="1" stroke-dasharray="2 9"`);
 b+=circle(330,226,145,'none',`stroke="${C.panel}" stroke-width="33"`);
 const len=2*Math.PI*145;
 b+=circle(330,226,145,'none',`stroke="${C.coral}" stroke-width="33" stroke-dasharray="${len*rate/100} ${len}" stroke-linecap="round" transform="rotate(-90 330 226)"`);
 b+=text(330,207,num(rate)+'%',68,C.coral,centered)+text(330,245,'หยุดยาลดน้ำตาลได้',20,C.text,centered)+text(330,277,'ที่จุดติดตาม 6 เดือน*',16,C.muted,centered);
 b+=line(483,227,533,227,C.coral)+circle(533,227,3,C.coral);
 b+=text(567,190,'96 / 718',33,C.text)+text(567,224,'คนที่ประเมินการหยุดยาได้',17,C.muted);
 b+=text(567,267,'95% CI',13,C.faint)+text(567,299,'11.1–16.1%',25,C.coral);
 b+=line(64,432,816,432)+text(64,466,'หยุดยาได้ ≠ ยืนยันภาวะเบาหวานระยะสงบ',17,C.muted)+text(816,466,'PROGRAMME COHORT',12,C.faint,end);
 return b;
}

export function cohorts(){
 let b='';
 const rows=[['โครงการ','PROGRAMME','995','20 แห่ง · ติดตาม 6 เดือน',C.coral],['ทะเบียน','REGISTRY','1,461','บ้านตาขุน · ชุดเปรียบเทียบ',C.mint],['สำรวจ 2566','SURVEY','214','เครือข่ายกระนวน · 3 เดือน',C.purple]];
 rows.forEach((r,i)=>{let x=35+i*276;b+=rect(x,35,258,292,C.panel,10)+rect(x,35,258,3,r[4])+text(x+22,77,r[1],12,r[4])+text(x+22,119,r[0],25)+text(x+22,204,r[2],54,r[4])+text(x+22,242,'คน',17,C.muted)+text(x+22,292,r[3],13,C.muted);});
 b+=text(47,378,'อีกด้านของหลักฐาน',16,C.muted)+text(47,420,'9 พื้นที่',29,C.text)+text(252,420,'89 ผู้ให้ข้อมูล',29,C.coral);
 b+=lines(532,390,['ผู้ให้บริการและผู้บริหาร 58 คน','ผู้ป่วย 31 คน'],17,C.muted,33);
 return b;
}

export function waffle(row){
 let b='';const pct=row.pct;
 for(let i=0;i<100;i++){const x=65+(i%10)*31,y=69+Math.floor(i/10)*31;const fill=i<Math.floor(pct)?C.coral:C.grid;b+=rect(x,y,22,22,fill,5);if(i===Math.floor(pct))b+=rect(x,y,22*(pct%1),22,C.coral,2);}
 b+=text(451,153,num(pct)+'%',76,C.coral)+text(453,199,`${num(row.events,0)} จาก ${num(row.n,0)} คน`,25)+text(453,240,`95% CI ${num(row.lo95)}–${num(row.hi95)}%`,19,C.muted);
 b+=line(453,270,803,270)+lines(453,310,['ฐานคำนวณตามผลลัพธ์ที่เลือก','จุดติดตาม 6 เดือนของกลุ่มโครงการ'],17,C.muted,32);
 b+=text(65,425,'1 ช่อง ≈ 1% ของผู้ที่ประเมินผลลัพธ์ได้',17,C.muted)+text(65,461,'ช่องสีเป็นภาพสัดส่วน ไม่ใช่ผู้ป่วยรายบุคคล',14,C.faint);
 return b;
}

export function paired(r,label){
 let b='';const lo=Math.min(r.pre_mean,r.post_mean)*.85,hi=Math.max(r.pre_mean,r.post_mean)*1.07;
 const y=v=>347-(v-lo)/(hi-lo)*244;
 for(let i=0;i<5;i++){let v=lo+(hi-lo)*i/4;b+=line(126,y(v),541,y(v))+text(111,y(v)+5,num(v,1),14,C.faint,end);}
 const a=y(r.pre_mean),z=y(r.post_mean);
 b+=line(228,a,466,z,C.coral,'stroke-width="4"')+circle(228,a,9,C.neutral)+circle(466,z,9,C.coral);
 b+=text(228,a-27,num(r.pre_mean,2),26,C.text,centered)+text(466,z-27,num(r.post_mean,2),26,C.coral,centered);
 b+=text(228,386,'ก่อนเข้าโครงการ',16,C.muted,centered)+text(466,386,'6 เดือน*',16,C.muted,centered);
 b+=text(628,137,'การเปลี่ยนแปลงเฉลี่ย',16,C.muted)+text(628,207,signed(r.mean_change),51,C.coral)+text(628,246,label==='HbA1c'?'จุดร้อยละ':r.unit,20,C.text);
 b+=text(628,295,'95% CI',14,C.faint)+text(628,327,`${signed(r.lo95)} ถึง ${signed(r.hi95)}`,19,C.muted)+text(628,379,`n = ${num(r.n_pairs,0)} คู่`,19,C.muted);
 b+=line(65,425,815,425)+text(65,460,'เปรียบเทียบก่อน–หลังในคนเดิม เฉพาะคู่ข้อมูลที่ครบ',16,C.muted);
 return b;
}

export const groups={
 g1:{code:'G1',label:'ยังไม่ใช้ยา · HbA1c > 6.5%',definition:'G1: ผู้ป่วยเบาหวานที่ยังไม่ใช้ยาลดน้ำตาลเมื่อเริ่มโครงการ และ HbA1c ตั้งต้น > 6.5% (89 คน) ไม่รวมผู้ที่ HbA1c ≤ 6.5% หรือไม่มีค่าเริ่มต้น'},
 g2:{code:'G2',label:'ใช้ยา · HbA1c ≥ 6.5%',definition:'G2: ใช้ยาลดน้ำตาลเมื่อเริ่มโครงการ และ HbA1c ตั้งต้น ≥ 6.5% (564 คน) รวมผู้ที่ HbA1c เท่ากับ 6.5% ตามนิยามกลุ่มเดิม'},
 g3:{code:'G3',label:'ใช้ยา · HbA1c < 6.5%',definition:'G3: ใช้ยาลดน้ำตาลเมื่อเริ่มโครงการ และ HbA1c ตั้งต้น < 6.5% (229 คน) เป็นกลุ่มที่ระดับน้ำตาลต่ำกว่าเกณฑ์ตั้งแต่เริ่มต้น'},
 non_insulin:{code:'G2a',label:'G2 · ไม่ใช้ insulin',definition:'G2a: กลุ่ม G2 ที่ไม่ใช้ insulin เมื่อเริ่มโครงการ (537 คน) ยังคงใช้ยาลดน้ำตาลชนิดอื่น ไม่ใช่กลุ่มไม่ใช้ยา'},
 insulin:{code:'G2b',label:'G2 · ใช้ insulin',definition:'G2b: กลุ่ม G2 ที่ใช้ insulin เมื่อเริ่มโครงการ (27 คน) อาจใช้ร่วมกับยาอื่น กลุ่มมีขนาดเล็กจึงควรอ่านช่วงความเชื่อมั่นประกอบ'}
};

export function subgroup(rows){
 let b='';const low=Math.min(0,...rows.map(r=>r.lo95)),high=Math.max(0,...rows.map(r=>r.hi95));
 const span=high-low||1,x=v=>375+(v-low+span*.14)/(span*1.28)*380,zero=x(0),dy=rows.length===4?83:108;
 b+=line(zero,64,zero,392,C.neutral,'stroke-dasharray="4 5"')+text(zero,43,'0',16,C.muted,centered);
 rows.forEach((r,i)=>{
  const y=99+i*dy,v=r.mean_change,co=v<0?C.coral:C.gold,g=groups[r.group];
  const label=tip(g.definition,text(40,y-12,g.code+' ⓘ',15,co)+text(40,y+16,g.label,16,C.text)+text(40,y+41,`ข้อมูลครบ ${num(r.n_pairs,0)} / ${num(r.n_group,0)} คน`,13,C.muted));
  const mark=rect(Math.min(x(v),zero),y-16,Math.abs(x(v)-zero),28,co,3,'opacity=".45"')+line(x(r.lo95),y-2,x(r.hi95),y-2,co,'stroke-width="2"')+circle(x(v),y-2,5,co)+text(831,y+5,signed(v),23,co,end);
  b+=label+tip(`${g.definition}\nเปลี่ยนแปลง ${signed(v)}; 95% CI ${signed(r.lo95)} ถึง ${signed(r.hi95)}\nคู่ข้อมูล ${r.n_pairs} คน`,mark);
 });
 b+=line(40,433,836,433)+text(40,465,'ค่าเฉลี่ยการเปลี่ยนแปลงและ 95% CI · ยังไม่ปรับปัจจัยกวน',15,C.muted);
 return b;
}

export function clinicalComparison(rows,metric){
 const low=Math.min(...rows.flatMap(r=>[r.pre_mean,r.post_mean])),high=Math.max(...rows.flatMap(r=>[r.pre_mean,r.post_mean]));
 const pad=Math.max((high-low)*.35,high*.035),min=low-pad,max=high+pad,y=v=>278-(v-min)/(max-min)*159;
 let b='';
 rows.forEach((r,i)=>{
  const offset=i*435,co=i?C.mint:C.coral,label=r.group==='gt65'?'HbA1c ตั้งต้น > 6.5%':'HbA1c ตั้งต้น ≤ 6.5%';
  b+=text(offset+230,42,label,23,co,centered)+text(offset+230,74,`คู่ข้อมูล ${num(r.n_pairs,0)} / ${num(r.n_group,0)} คน`,15,C.muted,centered);
  for(let j=0;j<4;j++){const value=min+(max-min)*j/3;b+=line(offset+102,y(value),offset+382,y(value))+text(offset+91,y(value)+4,num(value),12,C.faint,end);}
  const a=offset+150,z=offset+331;
  b+=line(a,y(r.pre_mean),z,y(r.post_mean),co,'stroke-width="3"')+circle(a,y(r.pre_mean),7,C.neutral)+circle(z,y(r.post_mean),7,co);
  b+=text(a,y(r.pre_mean)-18,num(r.pre_mean,2),21,C.text,centered)+text(z,y(r.post_mean)-18,num(r.post_mean,2),21,co,centered);
  b+=text(a,313,'ก่อน',16,C.muted,centered)+text(z,313,'6 เดือน*',16,C.muted,centered);
  b+=text(offset+230,369,signed(r.mean_change),39,co,centered)+text(offset+230,400,`95% CI ${signed(r.lo95)} ถึง ${signed(r.hi95)}`,16,C.muted,centered);
 });
 const unit=metric==='HbA1c'?'จุดร้อยละ':rows[0].unit;
 b+=line(440,95,440,410)+line(42,433,838,433)+text(440,467,`ความต่างของการเปลี่ยนแปลง (> 6.5 − ≤ 6.5): ${signed(rows[0].mean_change-rows[1].mean_change)} ${unit}`,18,C.text,centered);
 return b;
}

export function forest(rows,ci){
 const labels={'Age, per 10 years':'อายุ / 10 ปี','Female (vs male)':'หญิง (เทียบกับชาย)','Baseline HbA1c, per 1%':'HbA1c เริ่มต้น / 1 จุดร้อยละ','Baseline BMI, per 1 kg/m²':'BMI เริ่มต้น / 1 kg/m²','Baseline FBS, per 10 mg/dL':'FBS เริ่มต้น / 10 mg/dL','Baseline drug classes, per 1':'จำนวนกลุ่มยาเริ่มต้น / 1 กลุ่ม','On insulin at baseline':'ใช้อินซูลินก่อนเข้าโครงการ','Change in BMI at 6 mo, per 1 kg/m²':'BMI เปลี่ยนแปลง / 1 kg/m²','Change in waist at 6 mo, per 1 cm':'รอบเอวเปลี่ยนแปลง / 1 cm'};
 let b='';const x=v=>357+(Math.log10(v)+1)/Math.log10(60)*317;const dy=350/rows.length;
 for(const v of [.1,.25,.5,1,2,5])b+=line(x(v),44,x(v),410,v===1?C.neutral:C.grid,v===1?'stroke-dasharray="5 5"':'')+text(x(v),439,v,13,C.muted,centered);
 b+=text(806,27,'aOR  (95% CI)',14,C.muted,end);
 rows.forEach((r,i)=>{let y=65+i*dy;const highlight=r.term.includes('HbA1c')||r.term.includes('drug classes');const co=highlight?C.coral:C.neutral;b+=text(39,y+6,labels[r.term]||r.term,16,highlight?C.text:C.muted);if(ci)b+=line(x(r.lo95),y,x(r.hi95),y,co,'stroke-width="3"')+line(x(r.lo95),y-5,x(r.lo95),y+5,co)+line(x(r.hi95),y-5,x(r.hi95),y+5,co);b+=tip(`${labels[r.term]}: aOR ${num(r.OR,2)}; 95% CI ${num(r.lo95,2)}–${num(r.hi95,2)}`,circle(x(r.OR),y,highlight?7:5,co));b+=text(840,y+5,`${num(r.OR,2)} (${num(r.lo95,2)}–${num(r.hi95,2)})`,14,co,end);});
 b+=text(512,479,'← odds หยุดยาต่ำลง     |     odds สูงขึ้น →',15,C.muted,centered);
 return b;
}

export function sites(rows,ci){
 let b='';const x=v=>307+v*725;const dy=365/Math.max(rows.length,1);
 [0,.1,.2,.3,.4,.5,.6].forEach(v=>b+=line(x(v),31,x(v),425)+text(x(v),458,num(v*100,0)+'%',13,C.muted,centered));
 b+=line(x(96/718),30,x(96/718),425,C.coral,'stroke-dasharray="5 5" opacity=".5"');
 b+=text(839,19,'หยุดยา / n',13,C.muted,end);
 rows.forEach((r,i)=>{const y=47+i*dy;const p=r.k/r.n;const co=p>=96/718?C.coral:C.neutral;b+=text(282,y+5,r.facility,15,C.muted,end);if(ci)b+=line(x(r.lo),y,x(r.hi),y,co,'stroke-width="2"');b+=tip(`${r.facility}\n${r.k}/${r.n} คน = ${num(p*100)}%\n95% CI ${num(r.lo*100)}–${num(r.hi*100)}%`,circle(x(p),y,5,co));b+=text(845,y+5,`${r.k} / ${r.n}`,14,C.muted,end);});
 return b;
}

export function compare(r){
 let b='';const max=Math.max(Math.abs(r.programme),Math.abs(r.registry)) *1.3;const x=v=>450+v/max*284;
 b+=line(450,72,450,305,C.neutral,'stroke-dasharray="5 5"')+text(450,50,'0',15,C.muted,centered);
 [[r.programme,'โครงการ',r.n_prog,C.coral],[r.registry,'ทะเบียน',r.n_reg,C.mint]].forEach(([v,l,n,co],i)=>{let y=132+i*110;b+=text(47,y-3,l,23)+text(47,y+26,`n = ${num(n,0)} คู่`,15,C.muted);b+=rect(Math.min(450,x(v)),y-23,Math.abs(x(v)-450),39,co,4)+text(x(v)+(v<0?-13:13),y+6,signed(v),27,co,v<0?end:'');});
 b+=rect(49,338,780,119,C.panel,9)+text(72,373,'ความต่างของการเปลี่ยนแปลง: โครงการ − ทะเบียน',16,C.muted)+text(72,425,signed(r.difference),38,C.coral)+text(270,425,r.measure==='HbA1c'?'จุดร้อยละ':r.unit,18,C.muted)+text(797,392,`95% CI ${signed(r.lo95)} ถึง ${signed(r.hi95)}`,18,C.text,end)+text(797,427,r.p<.001?'p < 0.001':`p = ${num(r.p,3)}`,17,C.muted,end);
 return b;
}

export function provider(rows,ci){
 let b='';const x=v=>284+v*13.4;
 [0,10,20,30,40].forEach(v=>b+=line(x(v),75,x(v),343)+text(x(v),375,v+'%',15,C.muted,centered));
 rows.forEach((r,i)=>{const y=148+i*137,co=i?C.coral:C.mint;b+=text(43,y-5,i?'ปฐมภูมิ':'โรงพยาบาลชุมชน',21)+text(43,y+28,`${r.events} / ${r.n} คน`,17,C.muted);if(ci)b+=line(x(r.lo95),y,x(r.hi95),y,co,'stroke-width="4"')+line(x(r.lo95),y-9,x(r.lo95),y+9,co)+line(x(r.hi95),y-9,x(r.hi95),y+9,co);b+=circle(x(r.pct),y,9,co)+text(x(r.pct),y-28,num(r.pct)+'%',29,co,centered);});
 b+=text(440,449,'แบบบันทึกและระดับบริการแยกออกจากกันไม่ได้ในข้อมูลชุดนี้',17,C.muted,centered);return b;
}

export function costs(row,view){
 let b='';const co=[C.coral,C.mint];
 if(view==='paired'){
  const vals=[row.drug_change,row.lab_change,row.net_change],labs=['ค่ายา','ค่าตรวจ Lab','ผลรวมการเปลี่ยนแปลง'],cols=[C.coral,C.mint,C.gold];let max=Math.max(...vals.map(Math.abs))*1.24;const y=v=>241-v/max*161;
  b+=line(73,241,812,241,C.neutral);vals.forEach((v,i)=>{let x=179+i*252;b+=rect(x-45,Math.min(y(v),241),90,Math.abs(y(v)-241),cols[i],5)+text(x,v<0?y(v)+34:y(v)-15,signed(v,0),32,cols[i],centered)+text(x,432,labs[i],18,C.muted,centered);});
  b+=text(48,43,'การเปลี่ยนแปลงเฉลี่ยแบบจับคู่ · บาท / ครั้ง',17,C.muted);
 }else{
  const ymax=Math.max(row.drug_pre,row.drug_post,row.lab_pre,row.lab_post)*1.26;const y=v=>356-v/ymax*277;
  [0,.25,.5,.75,1].forEach(k=>b+=line(92,y(k*ymax),818,y(k*ymax))+text(78,y(k*ymax)+5,num(k*ymax,0),13,C.faint,end));
  [['ค่ายา',row.drug_pre,row.drug_post],['ค่าตรวจ Lab',row.lab_pre,row.lab_post]].forEach(([label,pre,post],i)=>{let x=271+i*344;[pre,post].forEach((v,j)=>{let xx=x-81+j*87;b+=rect(xx,y(v),68,356-y(v),j?co[i]:C.neutral,5)+text(xx+34,y(v)-13,num(v,0),26,j?co[i]:C.muted,centered);});b+=text(x,398,label,22,C.text,centered);});
  b+=circle(310,452,6,C.neutral)+text(327,458,'ก่อน',16,C.muted)+circle(443,452,6,C.coral)+text(460,458,'หลัง (สีตามหมวดค่าใช้จ่าย)',16,C.muted);
 }
 return b;
}

export function timing(rows){
 let b='';const labels={hba1c:'HbA1c',medication:'ข้อมูลยา',fbs:'FBS',bmi:'BMI',waist:'รอบเอว'};
 const order=['hba1c','medication','fbs','bmi','waist'];rows=[...rows].sort((a,b)=>order.indexOf(a.measure)-order.indexOf(b.measure));
 rows.forEach((r,i)=>{let y=72+i*71,x=209;const width=531;b+=text(46,y+23,labels[r.measure],20,C.text);['measured','labelled','assumed'].forEach((k,j)=>{const w=r[k]/r.total*width;b+=tip(`${labels[r.measure]} · ${k}: ${r[k]} / ${r.total} (${num(r[k]/r.total*100)}%)`,rect(x,y,w,33,[C.mint,C.purple,C.coral][j],2));if(w>75)b+=text(x+w/2,y+23,`${num(r[k]/r.total*100,0)}%`,16,C.bg,centered);x+=w;});b+=text(833,y+23,`n=${num(r.total,0)}`,15,C.muted,end);});
 [['มีวันที่วัด',C.mint,150],['ระบุเดือนในแบบบันทึก',C.purple,335],['อนุมานจากแบบบันทึก',C.coral,605]].forEach(([t,c,x])=>b+=circle(x,448,6,c)+text(x+16,454,t,15,C.muted));
 return b;
}

export const policies=[
 {short:'ชุดบริการพื้นฐาน',title:'มาตรฐานร่วม ยืดหยุ่นตามพื้นที่',body:['บูรณาการในบริการ NCD ตามปกติ','กำหนดองค์ประกอบขั้นต่ำและเกณฑ์ความปลอดภัย','สื่อสารว่า “ระยะสงบ” ยังต้องติดตามต่อ'],owner:'สธ. · องค์กรวิชาชีพ · กองทุนสุขภาพ',action:'เริ่มจากชุดบริการและนิยามผลลัพธ์ร่วม'},
 {short:'เส้นทางบริการ',title:'เลือกความเข้มข้นให้เหมาะกับชีวิต',body:['ประเมินความเสี่ยง ความพร้อม และความต้องการ','ปรับระดับการสนับสนุนได้ทั้งขึ้นและลง','ผู้มีโอกาสหยุดยาต่ำยังมีสิทธิได้รับการดูแล'],owner:'หน่วยบริการ · ทีมสหวิชาชีพ · ผู้ป่วย',action:'เริ่มจากเส้นทางบริการที่ตัดสินใจร่วมกัน'},
 {short:'การดูแลต่อเนื่อง',title:'เชื่อมโรงพยาบาลถึงครัวเรือน',body:['กำหนดผู้ประสานการดูแลและระบบส่งต่อ','มีช่องทางปรึกษาระหว่างทีมในเครือข่าย','รองรับสมุด โทรศัพท์ และช่องทางดิจิทัล'],owner:'เครือข่ายอำเภอ · รพ.สต. · ชุมชน',action:'เริ่มจากบทบาทและช่องทางติดตามที่ชัดเจน'},
 {short:'กำลังคนและองค์กร',title:'ให้ระบบรองรับทีมที่ทำงานจริง',body:['มีทีมสำรองและสมรรถนะขั้นต่ำร่วม','นับภาระงานให้รวมการติดตามนอกคลินิก','กระจายงานพร้อมเครื่องมือ เวลา และงบประมาณ'],owner:'ผู้บริหารหน่วยบริการ · สสจ. · ทีมดูแล',action:'เริ่มจากแผนกำลังคนและการนับภาระงาน'},
 {short:'การเงินการคลัง',title:'จ่ายให้การดูแลที่ทำให้ผลลัพธ์ยืนยาว',body:['มีงบพื้นฐานต่อเนื่องและการจ่ายแบบผสม','ให้คุณค่ากับกระบวนการและผลลัพธ์ระหว่างทาง','ปรับตามความซับซ้อนและทดลองก่อนขยาย'],owner:'กองทุนสุขภาพ · หน่วยบริการ · ผู้ประเมิน',action:'เริ่มจากนำร่องการจ่ายและเก็บต้นทุนจริง'},
 {short:'ระบบข้อมูล',title:'บันทึกครั้งเดียว ใช้ตัดสินใจหลายระดับ',body:['บันทึกวันที่เริ่ม วันที่หยุดยา และผลติดตาม','ใช้แบบข้อมูลร่วมเพื่อเทียบผลอย่างมีความหมาย','สะท้อนข้อมูลกลับสู่ผู้ป่วย ทีม และผู้ซื้อบริการ'],owner:'สธ. · หน่วยบริการ · กองทุน · นักวิจัย',action:'เริ่มจากชุดข้อมูลขั้นต่ำและระบบป้อนกลับ'},
 {short:'เงื่อนไขชีวิตและความเป็นธรรม',title:'ทำให้การดูแลเกิดขึ้นได้ในชีวิตจริง',body:['พิจารณาอาหาร เวลา งาน และการเดินทาง','เชื่อมท้องถิ่นและภาคส่วนอื่นตามบริบทพื้นที่','ติดตามว่ากลุ่มที่มีข้อจำกัดเข้าถึงประโยชน์หรือไม่'],owner:'ท้องถิ่น · กลไกอำเภอ · ชุมชน · ภาคี',action:'เริ่มจากปัญหาและทรัพยากรจริงของพื้นที่'}
];

export function policy(index){
 const p=policies[index];let b='';
 policies.forEach((p,i)=>{let y=44+i*55;const active=i===index;b+=rect(34,y,278,43,active?C.soft:C.panel,6)+text(51,y+28,String(i+1).padStart(2,'0'),15,active?C.coral:C.faint)+text(91,y+28,p.short,15,active?C.text:C.muted);});
 b+=rect(338,44,507,373,C.panel,10)+text(368,85,`POLICY ${String(index+1).padStart(2,'0')}`,13,C.coral)+text(368,130,p.title,21,C.text,bold);
 p.body.forEach((t,i)=>{b+=circle(373,182+i*52,3,C.coral)+text(388,188+i*52,t,16,C.muted);});
 b+=line(368,325,812,325)+text(368,356,'ผู้ร่วมขับเคลื่อน',12,C.faint)+text(368,390,p.owner,16,C.coral);
 b+=text(440,462,p.action,19,C.muted,centered);return b;
}

export function pathway(level){
 const nodes=[{x:48,t:'การสนับสนุนพื้นฐาน',n:'01',co:C.mint,a:['ทุกคนเข้าถึงได้','เป้าหมายที่ตกลงร่วมกัน'],b:'บริการ NCD ใกล้บ้าน'},{x:330,t:'การดูแลเข้มข้น',n:'02',co:C.coral,a:['เพิ่มการสนับสนุน','ตามความพร้อมและความเสี่ยง'],b:'ทีมสหวิชาชีพ'},{x:612,t:'การดูแลซับซ้อน',n:'03',co:C.purple,a:['เชื่อมผู้เชี่ยวชาญ','เมื่อมีข้อบ่งชี้ด้านความปลอดภัย'],b:'โรงพยาบาล / ทีมพร้อมดูแล'}];
 let b='';nodes.forEach((r,i)=>{const active=level==='all'||Number(level)===i;b+=rect(r.x,108,220,249,active?C.panel:C.bg,10,`stroke="${active?r.co:C.grid}"`)+text(r.x+21,151,r.n,16,active?r.co:C.faint)+text(r.x+21,196,r.t,20,active?C.text:C.muted)+lines(r.x+21,241,r.a,14,C.muted,28)+line(r.x+21,298,r.x+199,298)+text(r.x+21,332,r.b,13,active?r.co:C.muted);if(i<2)b+=text(r.x+251,244,'⇄',30,C.coral,centered);});
 b+=text(440,58,'เพิ่มหรือลดระดับได้ โดยไม่หลุดออกจากระบบ',23,C.text,centered)+text(440,412,'ผู้ป่วย + ครอบครัว + ทีมดูแล',23,C.coral,centered)+text(440,454,'ตัดสินใจร่วมกัน · ติดตามต่อเนื่อง · กลับเข้าสู่บริการได้',17,C.muted,centered);return b;
}

export function roadmap(focus){
 const rows=[{t:'วางฐานร่วม',s:'มาตรฐานบริการ + ข้อมูล',a:['นิยามผลลัพธ์และชุดบริการขั้นต่ำ','แบบบันทึกและวันที่สำคัญร่วมกัน'],c:C.coral},{t:'ทดลองให้ครบระบบ',s:'ทีมดูแล + เครือข่าย + การจ่าย',a:['นำร่องเส้นทางดูแลและการจ่ายแบบผสม','นับภาระงาน ต้นทุน และการเข้าถึง'],c:C.mint},{t:'เรียนรู้แล้วขยาย',s:'ผลลัพธ์ต่อเนื่อง + ความเป็นธรรม',a:['ติดตามผลลัพธ์และความปลอดภัยระยะยาว','ปรับระบบก่อนขยายสู่พื้นที่ใหม่'],c:C.purple}];let b='';
 b+=line(86,89,86,392,C.grid,'stroke-width="2"');
 rows.forEach((r,i)=>{const y=43+i*137,active=focus==='all'||Number(focus)===i;b+=circle(86,y+42,23,active?r.c:C.panel)+text(86,y+49,'0'+(i+1),18,active?C.bg:C.faint,centered)+text(136,y+29,r.t,24,active?C.text:C.muted)+text(136,y+62,r.s,15,active?r.c:C.muted)+lines(432,y+29,r.a,16,C.muted,32);if(i<2)b+=line(136,y+103,822,y+103);});
 b+=text(440,467,'ลำดับการขับเคลื่อนที่เสนอเพื่อหารือ · ไม่ใช่ผลการประเมิน',15,C.faint,centered);return b;
}
