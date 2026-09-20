(() => {
  const {node,button,savedTrips,render,exportTrip,toast}=window.TripUI;
  const root=document.getElementById('saved-list');
  function refresh(){root.replaceChildren();const items=savedTrips();if(!items.length){const empty=node('div',undefined,'empty-card');empty.append(node('h2','아직 저장한 여행이 없어요.'),node('p','여행을 만든 뒤 ‘여행 저장’을 눌러 주세요.'));const a=node('a','여행 만들기 →','primary-button');a.href='/';empty.append(a);root.append(empty);return;}
    for(const item of items){const t=item.itinerary,card=node('article',undefined,'saved-item');card.append(node('span',t.is_demo?'DEMO · 가상 코스':'SAVED TRIP','eyebrow'),node('h2',`${t.request.trip_days}일의 대전 여행`),node('p',`${t.request.start_point.name} → ${t.request.end_point.name}`),node('p',`반려견 ${t.request.dog_count}마리 · 주행 약 ${Math.round(t.total_drive_seconds/60)}분`),button('코스 보기','secondary-button',()=>{render(t);document.getElementById('result').scrollIntoView({behavior:'smooth'});}),button('내보내기','secondary-button',()=>exportTrip(t)),button('삭제','text-button',()=>{try{localStorage.setItem('dog-trips-v1',JSON.stringify(savedTrips().filter(x=>x.id!==item.id)));refresh();}catch{toast('저장한 여행을 삭제하지 못했습니다.');}}));root.append(card);}
  }refresh();
})();
