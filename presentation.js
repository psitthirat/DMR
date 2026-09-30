import {esc,num,signed,policies} from './charts.js';

const titles=[
 'เบาหวานระยะสงบ: จากหลักฐานสู่ระบบบริการ',
 'แหล่งข้อมูลและกรอบการวิเคราะห์',
 'ผลลัพธ์การหยุดยาและการควบคุมระดับน้ำตาล',
 'การเปลี่ยนแปลงตัวชี้วัดทางคลินิก',
 'ผลลัพธ์จำแนกตามสถานะเริ่มต้น',
 'ปัจจัยที่สัมพันธ์กับการหยุดยาลดน้ำตาล',
 'ความแตกต่างของผลลัพธ์ระหว่างหน่วยบริการ',
 'การเปรียบเทียบผลลัพธ์ระหว่างกลุ่มข้อมูล',
 'ผลลัพธ์จำแนกตามระดับบริการและแบบบันทึก',
 'การเปลี่ยนแปลงค่ายาและค่าตรวจทางห้องปฏิบัติการ',
 'ความครบถ้วนของข้อมูลเวลาติดตาม',
 'ข้อเสนอเชิงนโยบายเพื่อพัฒนาระบบบริการ',
 'เส้นทางบริการตามความต้องการของผู้ป่วย',
 'ลำดับการพัฒนาและขยายระบบบริการ'
];
const units={HbA1c:'จุดร้อยละ',FBS:'mg/dL',BMI:'kg/m²',Waist:'cm'};
const metricLabel={HbA1c:'HbA1c',FBS:'น้ำตาลอดอาหาร',BMI:'BMI',Waist:'รอบเอว'};
const cohortName={community_hospital:'โรงพยาบาลชุมชน',primary_care:'ปฐมภูมิ'};
const interval=(row,percentage=false)=>`${num(row.lo95)}–${num(row.hi95)}${percentage?'%':''}`;
const count=value=>num(value,0);
const table=(caption,headers,rows)=>`<table class="endpoint-table"><caption>${esc(caption)}</caption><thead><tr>${headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map((value,index)=>index===0?`<th scope="row">${esc(value)}</th>`:`<td>${esc(value)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;

export const titleFor=index=>titles[index]||'';

export function headlineFor(index,view={},state={}){
 const rows=view.rows||[],r=rows[0]||{};
 switch(index){
  case 0:return 'ผลวิเคราะห์โครงการและข้อเสนอเชิงนโยบายเพื่อการดูแลต่อเนื่อง';
  case 1:return 'ข้อมูลผู้ป่วยสามชุดและการสัมภาษณ์ใน 9 พื้นที่ใช้ตอบคำถามที่ต่างกัน';
  case 2:{
   const value=`${count(r.events)} จาก ${count(r.n)} คน (${num(r.pct)}%)`;
   if(state.outcome==='remission')return `ขอบเขตบนของระยะสงบ ${value} ยังยืนยันช่วงปลอดยาไม่ได้`;
   if(state.outcome==='control')return `HbA1c ต่ำกว่า 7% ที่จุดติดตาม 6 เดือน: ${value}`;
   return `หยุดยาลดน้ำตาลทั้งหมดที่จุดติดตาม 6 เดือน: ${value}`;
  }
  case 3:return `${metricLabel[state.metric]||state.metric} เปลี่ยนแปลงเฉลี่ย ${signed(r.mean_change)} ${units[state.metric]||r.unit} ในผู้มีข้อมูลครบ ${count(r.n_pairs)} คู่`;
  case 4:return `การเปลี่ยนแปลง ${metricLabel[state.metric]||state.metric} แตกต่างกันตามการใช้ยาและระดับน้ำตาลเริ่มต้น`;
  case 5:return 'HbA1c และจำนวนกลุ่มยาเริ่มต้นสัมพันธ์กับ odds ของการหยุดยา หลังปรับปัจจัยร่วม';
  case 6:return `แสดงผลจาก ${rows.length} หน่วยบริการที่มีผู้เข้าเกณฑ์อย่างน้อย ${state.min||8} คน`;
  case 7:return `${state.metric} เปลี่ยนแปลงต่างกัน ${signed(r.difference)} ${units[state.metric]} ระหว่างโครงการกับทะเบียน${state.anchor==='6 months'?'ที่ 6 เดือน':'เมื่อใช้ค่าติดตามล่าสุด'}`;
  case 8:return state.sample==='crf'?'เมื่อใช้เฉพาะ CRF ปฐมภูมิเหลือ 41 คนจาก 2 แห่ง; ความต่างยังไม่ชัดเจน':'อัตราหยุดยาดิบของปฐมภูมิสูงกว่า แต่ยังแยกผลของระดับบริการออกจากแบบบันทึกไม่ได้';
  case 9:{
   const group=state.group==='Stopped all drugs'?'กลุ่มหยุดยา':'กลุ่มยังใช้ยา';
   return state.view==='paired'?`${group}: ค่ายาเปลี่ยน ${signed(r.drug_change,0)} และค่าตรวจเปลี่ยน ${signed(r.lab_change,0)} บาทต่อครั้งแบบจับคู่`:`${group}: ค่ายาเฉลี่ย ${num(r.drug_pre,0)} → ${num(r.drug_post,0)} และค่าตรวจ ${num(r.lab_pre,0)} → ${num(r.lab_post,0)} บาทต่อครั้ง`;
  }
  case 10:return state.cohort==='registry'?'ทะเบียนมีวันตรวจทางคลินิก แต่ข้อมูลยาไม่มีวันที่สำหรับประเมินการหยุดยาที่ 6 เดือน':'กรอบเวลา 6 เดือนของ HbA1c และข้อมูลยาในโครงการส่วนใหญ่อนุมานจากแบบบันทึก';
  case 11:return policies[Number(state.policy)||0].title;
  case 12:return 'ปรับความเข้มข้นของการดูแลตามความเสี่ยง ความพร้อม และความต้องการ โดยติดตามต่อเนื่อง';
  case 13:return 'วางมาตรฐานร่วม ทดลองระบบบริการและการจ่าย แล้วติดตามผลก่อนขยาย';
  default:return view.summary||'';
 }
}

export function summaryTable(index,view={},state={}){
 const rows=view.rows||[],r=rows[0]||{};
 switch(index){
  case 1:return table('ฐานข้อมูลที่ใช้',['แหล่งข้อมูล','จำนวน'],rows.map(row=>[row.ชุดข้อมูล,`${count(row.จำนวน)} คน`]));
  case 2:return table('ผลลัพธ์ที่เลือก',['รายการ','ค่า'],[
   ['ผู้ที่ประเมินได้',`${count(r.n)} คน`],
   ['เข้าเกณฑ์ผลลัพธ์',`${count(r.events)} คน`],
   ['สัดส่วน',`${num(r.pct)}%`],
   ['95% CI',interval(r,true)]
  ]);
  case 3:return table(`ข้อมูลครบ ${count(r.n_pairs)} คู่`,['รายการ',state.metric==='HbA1c'?'ค่า':units[state.metric]],[
   ['ค่าเฉลี่ยก่อน',num(r.pre_mean,2)],
   ['ค่าเฉลี่ย 6 เดือน',num(r.post_mean,2)],
   ['เปลี่ยนแปลงเฉลี่ย',signed(r.mean_change)],
   ['95% CI ของการเปลี่ยนแปลง',`${signed(r.lo95)} ถึง ${signed(r.hi95)}`]
  ]);
  case 4:return table(`การเปลี่ยนแปลง ${state.metric} (${units[state.metric]})`,['กลุ่มเริ่มต้น','คู่ข้อมูล','เปลี่ยนแปลง'],rows.map((row,i)=>[
   ['G1 ยังไม่ใช้ยา','G2 ใช้ยา, HbA1c ≥ 6.5%','G3 ใช้ยา, HbA1c < 6.5%'][i],count(row[`${state.metric} n`]),signed(row[`Δ${state.metric}`])
  ]));
  case 5:return table(`แบบจำลอง ${state.model||'A'} · ปัจจัยสำคัญ`,['ปัจจัย','aOR (95% CI)'],rows.filter(row=>row.term==='Baseline HbA1c, per 1%'||row.term==='Baseline drug classes, per 1').map(row=>[
   row.term.includes('HbA1c')?'HbA1c / 1 จุดร้อยละ':'จำนวนยา / 1 กลุ่ม',`${num(row.OR,2)} (${num(row.lo95,2)}–${num(row.hi95,2)})`
  ]));
  case 6:{
   if(!rows.length)return '';
   const rates=rows.map(row=>row.k/row.n*100);
   return table('ขอบเขตข้อมูลที่แสดง',['รายการ','ค่า'],[
    ['หน่วยบริการ',`${rows.length} แห่ง`],
    ['ขนาดกลุ่มต่อแห่ง',`${count(Math.min(...rows.map(row=>row.n)))}–${count(Math.max(...rows.map(row=>row.n)))} คน`],
    ['ช่วงสัดส่วนดิบ',`${num(Math.min(...rates))}–${num(Math.max(...rates))}%`],
    ['โครงการรวม',`96/718 คน (13.4%)`]
   ]);
  }
  case 7:return table(`การเปลี่ยนแปลง ${state.metric} (${units[state.metric]})`,['รายการ','ค่า'],[
   [`โครงการ (${count(r.n_prog)} คู่)`,signed(r.programme)],
   [`ทะเบียน (${count(r.n_reg)} คู่)`,signed(r.registry)],
   ['โครงการ − ทะเบียน',signed(r.difference)],
   ['95% CI ของความต่าง',`${signed(r.lo95)} ถึง ${signed(r.hi95)}`]
  ]);
  case 8:return table(state.sample==='crf'?'เฉพาะแบบบันทึก CRF':'ทุกแบบบันทึก',['ระดับบริการ','หยุดยา / n','สัดส่วน'],rows.map(row=>[
   cohortName[row.outcome]||row.outcome,`${count(row.events)} / ${count(row.n)}`,`${num(row.pct)}%`
  ]));
  case 9:return state.view==='paired'?table('การเปลี่ยนแปลงจากคู่ข้อมูล · บาท/ครั้ง',['หมวดค่าใช้จ่าย','เปลี่ยนแปลง'],[
   ['ค่ายา',signed(r.drug_change,0)],
   ['ค่าตรวจทางห้องปฏิบัติการ',signed(r.lab_change,0)],
   ['ผลบวกของสองหมวด',signed(r.net_change,0)]
  ]):table('ค่าเฉลี่ยจากข้อมูลที่มีแต่ละช่วง · บาท/ครั้ง',['หมวดค่าใช้จ่าย','ก่อน','หลัง'],[
   ['ค่ายา',num(r.drug_pre,0),num(r.drug_post,0)],
   ['ค่าตรวจทางห้องปฏิบัติการ',num(r.lab_pre,0),num(r.lab_post,0)]
  ]);
  default:return '';
 }
}

export function metadataFor(index,view={},state={}){
 const rows=view.rows||[],r=rows[0]||{};
 const base={time:'จุดติดตาม 6 เดือน*',scope:'กลุ่มโครงการ',measure:'ผลลัพธ์ที่สังเกตได้',evidence:'ข้อมูลสังเกตการณ์',discussion:'*เวลาติดตามบางส่วนอนุมานจากแบบบันทึก'};
 switch(index){
  case 0:return {...base,time:'6 เดือน* และข้อเสนอระบบบริการ',scope:'โครงการ 995 คน · 20 หน่วยบริการ',measure:'ผลลัพธ์ผู้ป่วยและระบบบริการ',discussion:'ต้นแบบสำหรับการอภิปราย'};
  case 1:return {...base,time:'3 เดือน / 6 เดือน / ข้อมูลสัมภาษณ์',scope:'โครงการ · ทะเบียน · สำรวจ · สัมภาษณ์',measure:'หลักฐานเชิงปริมาณและเชิงคุณภาพ',discussion:'แต่ละชุดมีประชากรและวิธีบันทึกต่างกัน'};
  case 2:return {...base,scope:`ประเมินผลลัพธ์ได้ ${count(r.n)} คน`,measure:state.outcome==='remission'?'ระยะสงบ: ขอบเขตบน':state.outcome==='control'?'HbA1c < 7%':'หยุดยาลดน้ำตาลทั้งหมด',discussion:state.outcome==='remission'?'ไม่มีวันหยุดยาเพื่อยืนยันช่วงปลอดยา':'ตัวหารเปลี่ยนตามเกณฑ์และความครบถ้วนของข้อมูล'};
  case 3:return {...base,scope:`ข้อมูลครบ ${count(r.n_pairs)} คู่`,measure:`การเปลี่ยนแปลง ${state.metric}`,discussion:'เปรียบเทียบก่อน–หลัง ยังไม่ใช่ผลเชิงสาเหตุ'};
  case 4:return {...base,scope:'จำแนกกลุ่มได้ 907 คน',measure:`การเปลี่ยนแปลง ${state.metric} ตามกลุ่ม`,discussion:'อีก 88 คนจำแนกไม่ได้; ค่าเฉลี่ยยังไม่ปรับปัจจัยกวน'};
  case 5:return {...base,scope:`แบบจำลอง ${state.model||'A'} · GEE ตามหน่วยบริการ`,measure:'Adjusted odds ratio (aOR)',evidence:'การวิเคราะห์ปรับปัจจัยร่วม',discussion:'aOR ไม่ใช่ risk ratio และไม่ใช่ผลเชิงสาเหตุ'};
  case 6:return {...base,scope:`${rows.length} หน่วยบริการ · n ≥ ${state.min||8}`,measure:'สัดส่วนหยุดยาและ 95% CI',discussion:'ยังใช้จัดอันดับคุณภาพหน่วยบริการไม่ได้'};
  case 7:return {...base,time:state.anchor==='6 months'?'จุดติดตาม 6 เดือน* ร่วมกัน':'ค่าติดตามครั้งล่าสุด',scope:'โครงการและทะเบียนหนึ่งโรงพยาบาล',measure:`ความต่างของการเปลี่ยนแปลง ${state.metric}`,discussion:state.anchor==='6 months'?'ยังไม่ปรับปัจจัยกวนระหว่างกลุ่ม':'ช่วงเวลาติดตามต่างกัน; ใช้พิจารณาความไวของข้อสรุป'};
  case 8:return {...base,scope:state.sample==='crf'?'เฉพาะแบบ CRF':'ทุกแบบบันทึก',measure:'สัดส่วนหยุดยาแยกระดับบริการ',discussion:'ระดับบริการซ้อนทับกับชนิดแบบบันทึก'};
  case 9:return {...base,time:'ก่อน–หลัง · สถานะยาครั้งล่าสุด',scope:`ทะเบียนบ้านตาขุน · ขนาดกลุ่ม ${count(r.n)} คน`,measure:state.view==='paired'?'การเปลี่ยนแปลงแบบจับคู่ · บาท/ครั้ง':'ค่าเฉลี่ยในแต่ละช่วง · บาท/ครั้ง',discussion:state.view==='paired'?'จำนวนคู่ต่างกันตามหมวด; ผลบวกไม่ใช่ต้นทุนรวมบริการ':'ขนาดกลุ่มไม่ใช่จำนวนคู่; หักลบแทน paired change ไม่ได้'};
  case 10:return {...base,scope:state.cohort==='registry'?'กลุ่มทะเบียน':'กลุ่มโครงการ',measure:'ที่มาของกรอบเวลาตามตัวชี้วัด',discussion:'ตัวหารคือข้อมูลติดตามที่มีในแต่ละตัวชี้วัด'};
  case 11:return {time:'ร่างข้อเสนอเชิงนโยบาย',scope:'การสัมภาษณ์ 89 คน · 9 พื้นที่',measure:`ประเด็น ${Number(state.policy||0)+1} จาก 7 ประเด็น`,evidence:'ข้อเสนอเพื่อหารือ',discussion:'สังเคราะห์จากร่างนโยบาย ยังไม่ใช่นโยบายที่อนุมัติ'};
  case 12:return {time:'การออกแบบบริการต่อเนื่อง',scope:'ผู้ป่วย · ครอบครัว · เครือข่ายบริการ',measure:'เส้นทางบริการสามระดับ',evidence:'ข้อเสนอเพื่อหารือ',discussion:'ต้องพัฒนาเกณฑ์ความปลอดภัยร่วมกับทีมบริการ'};
  case 13:return {time:'ลำดับการพัฒนาที่เสนอ',scope:'มาตรฐาน · ระบบบริการ · การขยายผล',measure:'ผลลัพธ์ ความปลอดภัย ต้นทุน และการเข้าถึง',evidence:'ข้อเสนอเพื่อหารือ',discussion:'ลำดับการขับเคลื่อนเป็นข้อเสนอของสไลด์ฉบับร่าง'};
  default:return base;
 }
}
