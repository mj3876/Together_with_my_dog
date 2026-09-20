(() => {
  'use strict';
  let current = null, map = null, toastTimer;
  const $ = id => document.getElementById(id);
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const button = (text, cls, action) => { const b = node('button', text, cls); b.type = 'button'; b.addEventListener('click', action); return b; };
  const minutes = sec => Math.round(sec / 60);
  const clock = value => { const n = Math.round(value); return `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`; };
  function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 4500); }
  async function api(path, body) {
    const response = await fetch(path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(' / ') : data.detail;
      throw new Error(detail || '요청을 처리하지 못했습니다. 다시 시도해 주세요.');
    }
    return data;
  }
  function safeLink(label, url) {
    try { const u = new URL(url); if (!['http:', 'https:'].includes(u.protocol)) return null; const a = node('a', label, 'text-button'); a.href = u.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; } catch { return null; }
  }
  function savedTrips() { try { const data = JSON.parse(localStorage.getItem('dog-trips-v1') || '[]'); return Array.isArray(data) ? data.filter(x => x?.itinerary?.request && Array.isArray(x.itinerary.days)) : []; } catch { return []; } }
  function save(itinerary) {
    try { const items = savedTrips().filter(x => x.itinerary.integrity_token !== itinerary.integrity_token); items.unshift({id: String(Date.now()), saved_at: new Date().toISOString(), itinerary}); localStorage.setItem('dog-trips-v1', JSON.stringify(items.slice(0, 20))); toast('이 브라우저에 여행을 저장했어요.'); }
    catch { toast('브라우저 저장 공간을 사용할 수 없습니다. JSON 내보내기를 이용해 주세요.'); }
  }
  function exportTrip(itinerary) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(itinerary, null, 2)], {type:'application/json'}));
    const a = node('a'); a.href = url; a.download = `daejeon-${itinerary.request.trip_days}days${itinerary.is_demo ? '-DEMO' : ''}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function openDialog(content) { $('detail-content').replaceChildren(content); $('detail-dialog').showModal(); }
  function detail(place) {
    const content = node('div'); content.append(node('span', category(place.category), 'eyebrow'), node('h2', place.name), node('p', place.address), node('p', place.description));
    if (place.product_name) content.append(node('h3', place.product_name));
    const policy = place.policy, info = node('section', undefined, 'info-panel');
    info.append(node('h3', '반려견 동반 규정'), node('p', `마릿수: ${policy.dogs_unlimited ? '제한 없음' : policy.max_dogs ? `최대 ${policy.max_dogs}마리` : '미확인'}`),
      node('p', `각 체중: ${policy.weight_unlimited ? '제한 없음' : policy.max_weight_kg ? `${policy.max_weight_kg}kg ${policy.weight_operator === 'lt' ? '미만' : '이하'}` : '미확인'}`),
      node('p', `확인일: ${policy.checked_at || '미확인'}`), node('p', policy.source_quote));
    if (!place.is_demo && policy.source_url) { const a = safeLink('규정 출처 ↗', policy.source_url); if (a) info.append(a); }
    const list = node('ul'); for (const r of policy.requirements) list.append(node('li', r)); info.append(list, node('p', place.schedule_note));
    if (place.price_note) info.append(node('p', `참고 요금: ${place.price_note}`));
    content.append(info, node('p', '견종·인원·준비물·날짜별 영업과 예약 가능 여부는 방문 전에 확인해 주세요.'));
    if (!place.is_demo && place.official_url) { const a = safeLink('공식 안내·예약 ↗', place.official_url); if (a) content.append(a); }
    openDialog(content);
  }
  function category(value) { return {lodging:'숙소', restaurant:'식당', activity:'체험'}[value] || value; }
  async function replace(slot, day) {
    const root = $('result'); const buttons = [...root.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true); root.setAttribute('aria-busy','true');
    toast('다른 장소를 포함한 코스 하나를 계산하고 있어요.');
    try {
      const data = await api('/api/v1/itineraries/replace', {itinerary: current, slot, day_number: day});
      if (data.itinerary) { render(data.itinerary); toast('새로운 코스로 갱신했어요.'); }
      else toast(`현재 코스를 유지합니다. ${data.reasons.join(' ')}`);
    } catch (e) { toast(e.message); }
    finally { buttons.forEach(b => b.disabled = false); root.removeAttribute('aria-busy'); }
  }
  function placeCard(place, start, end, day) {
    const card = node('li', undefined, `stop-card ${place.category === 'lodging' ? 'lodging-card' : ''}`);
    const head = node('header'); head.append(node('span', category(place.category), 'category-tag'), node('span', start === null ? '거점 연박' : `${clock(start)} – ${clock(end)}`));
    card.append(head, node('h3', place.name), node('p', place.product_name || place.address));
    const actions = node('div', undefined, 'card-buttons'); actions.append(button('장소 상세 보기', 'text-button', () => detail(place)), button(`${category(place.category)} 바꾸기`, 'text-button', () => replace(place.category, day)));
    card.append(actions); return card;
  }
  function drawMap(day) {
    if (map) { map.remove(); map = null; }
    const container = $('route-map'); container.replaceChildren();
    const points = [day.start_point, ...day.stops.map(s => s.place), day.end_point];
    if (window.L) {
      map = L.map(container, {scrollWheelZoom:false}).setView([36.35,127.38],12);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
      for (const [i,p] of points.entries()) L.marker([p.latitude,p.longitude]).addTo(map).bindPopup(node('span', `${i + 1}. ${p.name}`));
      for (const leg of day.route_legs) {
        const coords = leg.geometry.length ? leg.geometry : [[leg.origin.latitude,leg.origin.longitude],[leg.destination.latitude,leg.destination.longitude]];
        L.polyline(coords, {color:'#416848', weight:4, opacity:.8, dashArray:leg.geometry.length ? null : '7 8'}).addTo(map);
      }
      map.fitBounds(points.map(p => [p.latitude,p.longitude]), {padding:[35,35],maxZoom:14});
    } else {
      // An offline position overview; explicitly not a road map.
      const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns,'svg'); svg.setAttribute('viewBox','0 0 440 380'); svg.classList.add('map-fallback'); svg.setAttribute('aria-label','지도 연결 없이 표시하는 장소 위치 개요');
      const xs = points.map(p => p.longitude), ys = points.map(p => p.latitude), xmin=Math.min(...xs), xmax=Math.max(...xs), ymin=Math.min(...ys), ymax=Math.max(...ys);
      const coords=points.map(p => [45+(p.longitude-xmin)/(xmax-xmin||1)*320, 315-(p.latitude-ymin)/(ymax-ymin||1)*240]);
      const path=document.createElementNS(ns,'polyline'); path.setAttribute('points',coords.map(p=>p.join(',')).join(' ')); path.setAttribute('fill','none'); path.setAttribute('stroke','#84997c'); path.setAttribute('stroke-width','3'); path.setAttribute('stroke-dasharray','6 8'); svg.append(path);
      coords.forEach(([x,y],i)=>{const circle=document.createElementNS(ns,'circle');circle.setAttribute('cx',x);circle.setAttribute('cy',y);circle.setAttribute('r','8');circle.setAttribute('fill','#285640');svg.append(circle);const text=document.createElementNS(ns,'text');text.setAttribute('x',x+12);text.setAttribute('y',y-12);text.textContent=`${i+1}. ${points[i].name}`;svg.append(text);}); container.append(svg);
    }
  }
  function showDay(index) {
    const day=current.days[index]; const panel=$('day-content'); panel.replaceChildren();
    $('day-tabs').querySelectorAll('button').forEach((b,i)=>b.setAttribute('aria-selected',String(i===index)));
    panel.append(node('div', `${day.day_number}일차 · ${clock(day.start_minute)}–${clock(day.end_minute)} 예시 · 주행 ${minutes(day.total_drive_seconds)}분`, 'day-meta'));
    panel.append(node('div', `출발 · ${day.start_point.name}`, 'endpoint'));
    const timeline=node('ol',undefined,'timeline');
    day.stops.forEach((stop,i)=>{
      timeline.append(node('li', `↓ 자동차 약 ${minutes(day.route_legs[i].duration_seconds)}분 · 준비 10분${stop.wait_minutes > 0 ? ` · 대기 ${Math.round(stop.wait_minutes)}분` : ''}`, 'drive-line'));
      timeline.append(placeCard(stop.place,stop.start_minute,stop.end_minute,day.day_number));
    });
    timeline.append(node('li', `↓ 자동차 약 ${minutes(day.route_legs[2].duration_seconds)}분 · 준비 10분${day.lodging_wait_minutes > 0 ? ` · 체크인 대기 ${Math.round(day.lodging_wait_minutes)}분` : ''}`,'drive-line'));
    panel.append(timeline,node('div', `${day.day_number === current.request.trip_days ? '여행 종료' : '숙소 도착'} · ${day.end_point.name}`, 'endpoint'));
    if(current.lodging_room) {const ul=node('ul',undefined,'timeline');ul.append(placeCard(current.lodging_room,null,null,1));panel.append(ul);}
    drawMap(day);
  }
  async function inquiries() {
    try { const data=await api('/api/v1/itineraries/inquiry',{itinerary:current});const content=node('div');content.append(node('h2','방문 전 문의 문안'),node('p','필요한 문안을 복사해 공식 채널에 직접 문의해 주세요. 자동 발송되지 않습니다.'));
      for(const item of data.messages){content.append(node('h3',item.name),node('pre',item.text,'inquiry-text'),button('문안 복사','secondary-button',async()=>{try{await navigator.clipboard.writeText(item.text);toast('복사했어요.');}catch{toast('위 문안을 선택해 직접 복사해 주세요.');}}));}openDialog(content);
    } catch(e){toast(e.message);}
  }
  function render(itinerary) {
    if(map){map.remove();map=null;}
    current=itinerary;const root=$('result');root.hidden=false;root.replaceChildren();
    const heading=node('div',undefined,'result-heading'),copy=node('div');copy.append(node('span','YOUR ONE & ONLY ROUTE','eyebrow'),node('h2',`${itinerary.request.trip_days}일, 함께할 대전 여행`),node('p',`${itinerary.request.start_point.name}에서 ${itinerary.request.end_point.name}까지`));
    const actions=node('div',undefined,'result-actions');actions.append(button('여행 저장','secondary-button',()=>save(current)),button('JSON 내보내기','secondary-button',()=>exportTrip(current)),button('문의 문안','secondary-button',inquiries));heading.append(copy,actions);root.append(heading);
    if(itinerary.is_demo)root.append(node('div','데모 코스 · 업체·규정·이동시간이 모두 가상이며 실제 방문용이 아닙니다.','notice'));
    const stats=node('div',undefined,'result-summary');for(const text of [`총 주행 약 ${minutes(itinerary.total_drive_seconds)}분`, `반려견 ${itinerary.request.dog_count}마리`,itinerary.nights ? `${itinerary.nights}박 · 한 숙소에서 연박`:'숙박 없는 당일 여행',`가장 긴 이동 ${minutes(itinerary.max_leg_seconds)}분`])stats.append(node('span',text,'stat-pill'));root.append(stats);
    const tabs=node('div',undefined,'day-tabs');tabs.id='day-tabs';tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','같은 여행의 일차별 일정');itinerary.days.forEach((d,i)=>{const b=button(`${d.day_number}일차`,'day-tab',()=>showDay(i));b.setAttribute('role','tab');b.setAttribute('aria-controls','day-content');tabs.append(b);});root.append(tabs);
    const grid=node('div',undefined,'result-grid'),mapPanel=node('div',undefined,'map-panel'),mapBox=node('div',undefined,'map-box');mapBox.id='route-map';mapPanel.append(mapBox,node('p','실선은 조회한 도로 경로, 점선은 방문 순서 연결선입니다. 지도 연결이 없으면 위치 개요를 표시합니다.','map-caption'));const dayPanel=node('section');dayPanel.id='day-content';dayPanel.setAttribute('role','tabpanel');grid.append(mapPanel,dayPanel);root.append(grid);
    const why=node('div',undefined,'info-panel');why.append(node('h3','이 코스를 선정한 이유'));const reasons=node('ul');itinerary.reasons.forEach(r=>reasons.append(node('li',r)));why.append(reasons);root.append(why);
    for(const [title,items] of [['계획에 적용한 기준',itinerary.planning_basis],['방문 전 확인사항',itinerary.visit_requirements]]){const details=node('details',undefined,'info-panel');details.append(node('summary',title));const list=node('ul');items.forEach(r=>list.append(node('li',r)));details.append(list);root.append(details);}
    showDay(0);
  }
  document.querySelector('.dialog-close')?.addEventListener('click',()=>$('detail-dialog').close());
  window.TripUI={api,node,button,toast,render,savedTrips,save,exportTrip};
})();
