import {C, esc, text, rect} from './charts.js';

const title = ['เบาหวานระยะสงบ', 'จากหลักฐาน สู่ระบบบริการ'];
const project = 'ผลการวิเคราะห์โครงการและข้อเสนอเชิงนโยบายเพื่อการดูแลที่ต่อเนื่องและเป็นธรรม';
const subtitle = ['ข้อมูลโครงการ 995 คน จาก 20 หน่วยบริการ', 'ร่วมกับข้อค้นพบจากการสัมภาษณ์ 9 พื้นที่'];
const topics = ['ผลลัพธ์ของผู้ป่วย', 'ความต่อเนื่องของการดูแล', 'ข้อเสนอเชิงระบบ'];

// A fixed seed keeps the quiet star field identical across views and downloads.
// The field is decorative: no points or paths represent study observations.
function backdrop(id) {
  let seed = 73119;
  const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);
  const dots = [];
  for (let i = 0; i < 120; i++) {
    const x = random() * 1440;
    const y = random() * 900;
    const r = .35 + random() * .6;
    const opacity = .06 + random() * .22;
    dots.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r.toFixed(2)}" fill="${i % 5 ? C.muted : C.coral}" opacity="${opacity.toFixed(2)}"/>`);
  }
  // Loose orbital arcs disappear toward the reading area on the left.
  for (let i = 0; i < 230; i++) {
    const angle = random() * Math.PI * 2;
    const radius = .58 + random() * .67;
    const x = Math.cos(angle) * 425 * radius;
    const y = Math.sin(angle) * 156 * radius;
    const cx = 1190 + x * .83 + y * .56;
    const cy = 530 - x * .56 + y * .83;
    const r = .32 + random() * .6;
    const opacity = .1 + random() * .25;
    dots.push(`<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${r.toFixed(2)}" fill="${i % 4 ? C.muted : C.coral}" opacity="${opacity.toFixed(2)}"/>`);
  }
  return `<defs>
    <radialGradient id="${id}-haze"><stop stop-color="${C.coral}" stop-opacity=".065"/><stop offset=".48" stop-color="${C.purple}" stop-opacity=".025"/><stop offset="1" stop-color="${C.bg}" stop-opacity="0"/></radialGradient>
    <linearGradient id="${id}-fade"><stop stop-color="white" stop-opacity=".18"/><stop offset=".48" stop-color="white" stop-opacity=".44"/><stop offset="1" stop-color="white"/></linearGradient>
    <mask id="${id}-mask"><rect width="1440" height="900" fill="url(#${id}-fade)"/></mask>
  </defs>
  <ellipse cx="1190" cy="530" rx="560" ry="245" transform="rotate(-34 1190 530)" fill="url(#${id}-haze)"/>
  <g mask="url(#${id}-mask)">${dots.join('')}</g>`;
}

export function coverMarkup() {
  return `<section class="titlecard" aria-label="${esc(title.join(' '))}">
    <div class="titlecard__backdrop" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">${backdrop('dmr-cover')}</svg></div>
    <div class="titlecard__content">
      <h1 class="titlecard__title"><span>${esc(title[0])}</span><span class="titlecard__accent">${esc(title[1])}</span></h1>
      <p class="titlecard__project">${esc(project)}</p>
      <p class="titlecard__subtitle">${subtitle.map(esc).join('<br>')}</p>
      <ul class="titlecard__topics" aria-label="ประเด็นการนำเสนอ">${topics.map(topic => `<li>${esc(topic)}</li>`).join('')}</ul>
    </div>
  </section>`;
}

export function coverFigure() {
  let body = `<svg x="0" y="0" width="880" height="490" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">${backdrop('dmr-cover-export')}</svg>`;
  body += text(48, 122, title[0], 45, C.text, 'font-weight="600"');
  body += text(48, 184, title[1], 43, C.coral, 'font-weight="600"');
  body += text(48, 244, 'ผลการวิเคราะห์โครงการและข้อเสนอเชิงนโยบาย', 19, C.muted);
  body += text(48, 274, 'เพื่อการดูแลที่ต่อเนื่องและเป็นธรรม', 19, C.muted);
  subtitle.forEach((value, i) => { body += text(48, 337 + i * 29, value, 18, C.text); });
  let x = 48;
  const positions = [48, 254, 520];
  topics.forEach((topic, i) => {
    x = positions[i];
    if (i) body += rect(x - 22, 409, 1, 19, C.grid);
    body += text(x, 425, topic, 16, C.muted);
  });
  return body;
}
