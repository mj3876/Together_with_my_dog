(() => {
  'use strict';
  const {api,node,button,toast,render}=window.TripUI;
  const $=id=>document.getElementById(id);
  const chosen={start:null,end:null}, sequence={start:0,end:0}, timers={};
  let lastWeightCount=1;
  function choose(which, point){chosen[which]=point;$(which+'-search').value=point.name;$(which+'-selection').textContent=`선택됨 · ${point.address || point.name}`;$(which+'-selection').classList.add('confirmed');$(which+'-options').replaceChildren();sequence[which]++;}
  async function search(which, query){const ticket=++sequence[which];try{const data=await api('/api/v1/locations?q='+encodeURIComponent(query));if(ticket!==sequence[which])return;const root=$(which+'-options');root.replaceChildren();for(const p of data.items){const b=button(p.name,'location-option',()=>choose(which,p));if(query)b.append(node('small',p.address));root.append(b);}if(!data.items.length)$(which+'-selection').textContent=data.search_connected?'대전 내 다른 장소명이나 주소로 검색해 주세요.':'장소 검색 연결 전입니다. 대전역·유성온천역·대전시청을 선택할 수 있어요.';}catch(e){if(ticket===sequence[which])$(which+'-selection').textContent=e.message;}}
  for(const which of ['start','end']){const input=$(which+'-search');input.addEventListener('input',()=>{chosen[which]=null;sequence[which]++;$(which+'-selection').textContent='검색 결과에서 위치를 선택해 주세요.';$(which+'-selection').classList.remove('confirmed');clearTimeout(timers[which]);timers[which]=setTimeout(()=>search(which,input.value.trim()),300);});search(which,'');}
  $('same-location').addEventListener('click',()=>{if(!chosen.start){toast('출발 위치를 먼저 선택해 주세요.');$('start-search').focus();return;}choose('end',chosen.start);});
  document.querySelectorAll('.locate').forEach(b=>b.addEventListener('click',()=>{if(!navigator.geolocation){toast('현재 위치를 사용할 수 없는 브라우저입니다.');return;}b.disabled=true;navigator.geolocation.getCurrentPosition(async p=>{try{const result=await api(`/api/v1/locations/resolve?latitude=${p.coords.latitude}&longitude=${p.coords.longitude}`);choose(b.dataset.target,result);}catch(e){toast(e.message);}finally{b.disabled=false;}},()=>{toast('현재 위치를 가져오지 못했습니다. 장소 검색을 이용해 주세요.');b.disabled=false;},{timeout:10000,maximumAge:60000});}));
  $('trip-days').addEventListener('input',()=>{const n=Number($('trip-days').value);$('nights-label').textContent=Number.isInteger(n)&&n>0?(n===1?'숙박 없는 당일 여행':`${n-1}박 ${n}일 여행`):'1일 이상 입력해 주세요.';});
  $('dog-count').addEventListener('input',()=>{const count=Number($('dog-count').value);if(!Number.isInteger(count)||count<1||count>100||count===lastWeightCount)return;const old=[...document.querySelectorAll('.dog-weight')].map(i=>i.value);$('dog-weights').replaceChildren();for(let i=0;i<count;i++){const item=node('div',undefined,'weight-item'),label=node('label',`반려견 ${i+1}`);label.htmlFor=`weight-${i}`;const unit=node('div',undefined,'unit-input'),input=node('input');input.type='number';input.id=`weight-${i}`;input.className='dog-weight';input.min='.1';input.step='.1';input.required=true;input.placeholder='예: 7.5';input.value=old[i]||'';unit.append(input,node('span','kg'));item.append(label,unit);$('dog-weights').append(item);}lastWeightCount=count;});
  $('trip-form').addEventListener('submit',async e=>{e.preventDefault();$('form-error').hidden=true;const days=Number($('trip-days').value),count=Number($('dog-count').value),weights=[...document.querySelectorAll('.dog-weight')].map(i=>Number(i.value));let error='',focus=null;
    if(!chosen.start){error='출발 위치를 검색 결과에서 선택해 주세요.';focus=$('start-search');}
    else if(!Number.isInteger(days)||days<1){error='여행 일수는 1 이상의 정수로 입력해 주세요.';focus=$('trip-days');}
    else if(!Number.isInteger(count)||count<1||count>100){error='반려견 수를 1~100마리 범위의 정수로 입력해 주세요.';focus=$('dog-count');}
    else if(weights.length!==count||weights.some(w=>!Number.isFinite(w)||w<=0||Math.abs(w*10-Math.round(w*10))>1e-7)){error='각 반려견의 체중을 소수점 한 자리까지 입력해 주세요.';focus=$('weight-0');}
    else if(!chosen.end){error='여행 종료 위치를 검색 결과에서 선택해 주세요.';focus=$('end-search');}
    if(error){$('form-error').textContent=error;$('form-error').hidden=false;focus?.focus();return;}
    const request={start_point:chosen.start,trip_days:days,dog_count:count,dog_weights_kg:weights,end_point:chosen.end};
    $('trip-fields').disabled=true;$('loading').hidden=false;$('empty-result').hidden=true;$('result').hidden=true;$('create-trip').textContent='코스를 만들고 있어요…';
    try{const data=await api('/api/v1/recommendations',request);if(data.itinerary){render(data.itinerary);$('result').scrollIntoView({behavior:'smooth',block:'start'});}else{const box=$('empty-result');box.replaceChildren(node('span','아직 완성할 수 없는 여행','eyebrow'),node('h2','조건에 맞는 코스를 만들지 못했어요.'));const ul=node('ul');data.reasons.forEach(r=>ul.append(node('li',r)));box.append(ul,node('p','추가 설문은 필요하지 않아요. 등록된 장소와 이동정보가 충분해야 코스를 만들 수 있습니다.'));box.hidden=false;box.scrollIntoView({behavior:'smooth',block:'center'});}}
    catch(err){$('form-error').textContent=err.message;$('form-error').hidden=false;}
    finally{$('trip-fields').disabled=false;$('loading').hidden=true;$('create-trip').textContent='내 여행 코스 만들기 →';}
  });
})();
