import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const outputDir = 'C:/Users/ms840/mjuser/Together_with_my_dog/outputs/wbs_20260924_0930';
const previewDir = 'C:/Users/ms840/mjuser/Together_with_my_dog/tmp/wbs_20260924_0930';
const tasks = [
 ['1.1',24,'착수','필수 기능·역할·완료 기준 확정','공동','기존 대전 앱 기준의 필수/제외 기능 목록, A/B 담당 확정'],
 ['1.2',24,'개발','기존 앱 실행 및 미완성 기능 점검','A','입력→추천→상세→저장 흐름별 수정 목록과 우선순위'],
 ['1.3',24,'개발','실제 데이터·지도·경로 API 연결 점검','A','실제 모드 실행 확인, 연결 오류와 필요한 설정 목록'],
 ['1.4',24,'데이터','지역 선정 자료와 분석 기준 점검','B','비교 지역·기간·행정단위·지표 확정, 보완자료 목록'],
 ['1.5',24,'데이터·검증','장소 조사 목록·외부 평가 일정 확보','B','숙소·식당·체험 조사표, 보호자 2명 9/27 오전 참여 목표'],
 ['1.6',24,'제출 준비','공모 양식·신청 항목·파일 규격 확인','B','필수서류·서명·첨부 규격 체크리스트. 본문 제작은 9/28부터'],
 ['2.1',25,'개발','입력 검증·반려견 조건 판정 보완','A','개별 체중·마릿수·경계값·규정 누락 처리'],
 ['2.2',25,'개발','당일·숙박 코스와 이동시간 계산 완성','A','일수별 구성, 출발/종료 포함 경로, 최종 코스 1개, 후보 부족 처리'],
 ['2.3',25,'데이터','실제 장소·동반 규정 검토본 전달','B','공식 출처·확인일·객실/공간/프로그램별 규정. A에게 적재본 전달'],
 ['2.4',25,'분석','지역 비교 결과·대전 선정 근거 확정','B','분석 결과표, 선정/제외 이유, 기간·비교단위·API 등록 편차 한계'],
 ['2.5',25,'검증 준비','평가 사례·정답·사용자 과제 확정','B','개발용 약 10건과 최종 평가 약 30건 분리. 비교 과제·기록지 잠금'],
 ['3.1',26,'개발','결과·장소 변경·저장·문의 기능 통합','A','실제 데이터로 전체 흐름 연결, 출처·미확인·오류 안내 표시'],
 ['3.2',26,'배포','평가 환경 확보·평가 버전 고정','A','오전 통합 후 평가용 접속/실행 확인, 코드·데이터 버전 기록'],
 ['3.3',26,'성과검증','고정 기술 평가 실행·첫 결과 보존','B','3.2 완료 후 사례별 입력·정답·결과·오류·실행 버전 저장'],
 ['3.4',26,'검증 준비','사용자 과제 리허설·기록 환경 점검','B','비교 도구·시간 한도·완료 기준 통일, 9/27 참여 일정 재확인'],
 ['3.5',26,'개발','기술 평가의 치명적 오류 수정','A','3.3 결과 전달 후 수정. 첫 결과와 수정 이력 분리 보존'],
 ['4.1',27,'성과검증','외부 보호자 비교 과제 진행','B','오전 고정 버전으로 일반 검색/서비스 완성 여부·시간·오류·도움 기록'],
 ['4.2',27,'안정화','핵심 오류 수정·최종 회귀 점검','A','평가 중 버전 유지. 평가 후 수정본의 입력·코스·경로·저장 재검증'],
 ['4.3',27,'성과검증','실측 결과·한계·보고 수치 확정','B','분자·분모·참여자·버전 명시. 첫 평가와 수정 후 결과 구분'],
 ['4.4',27,'시연','최종 앱 안정화·시연 자료 제작','A','4.2 후 최종 실행본과 성공·불가/정보 부족 사례 화면·영상 확보'],
 ['4.5',27,'마일스톤','앱·데이터·시연·성과 원자료 최종 고정','공동','당일 종료 전 버전·실행 안내·영상·평가 원자료 백업. 개발 완료'],
 ['5.1',28,'자료 제작','지역 선정·데이터 활용 설명자료 작성','B','원자료→정제→분석→대전 선정→서비스 적용, 도표·출처·한계 정리'],
 ['5.2',28,'자료 제작','구현 구조·기능·시연 설명자료 작성','A','9/27 확정 화면/영상으로 서비스 흐름·구현 내용·기능별 증빙 설명'],
 ['5.3',28,'자료 제작','성과검증 보고서·성과표 작성','B','9/27 확정 원자료로 측정 방법·결과·오류·한계 작성. 기대효과 분리'],
 ['5.4',28,'자료 제작','활용사례 본문 1차 통합·증빙 연결','공동','서식4의 문제·데이터 활용·적용·성과 초안과 증빙 파일 연결'],
 ['6.1',29,'자료 제작','활용사례 작성양식 최종 편집','B','서식4 2~3쪽, 함초롱바탕 11pt·줄간격 160, 성과분야 1개 선택'],
 ['6.2',29,'서류','신청서·동의서·확인서 작성 및 서명','B 주도·공동 서명','서식1-1·2·3의 인적사항 확인, 대표·공동참가자 본인 서명'],
 ['6.3',29,'서류','제출 PDF 변환·서식 검수','B','서식1-1·2·3·4 PDF, 글자·쪽수·서명·필수 항목 확인'],
 ['6.4',29,'증빙','참고자료 ZIP·원본 백업 정리','A','지역 분석·성과표·평가 원자료·시연 증빙과 파일 목록. 제출용 비밀키·개인정보 제외'],
 ['6.5',29,'마일스톤','최종 제출 패키지 교차 검수','공동','본문·성과표 수치 일치, PDF/ZIP 열기, 링크·용량·파일명·누락 점검'],
 ['7.1',30,'최종 확인','제출 파일·링크·실행 상태 확인','A','오전 최종 점검. 신규 기능·새 성과 측정은 배정하지 않음'],
 ['7.2',30,'제출','온라인 신청·파일 업로드','B','11:00까지 제출 목표, 공식 마감 14:00(KST). 접수 화면 보관'],
 ['7.3',30,'접수 확인','접수 내용 교차 확인·오류 대응','공동','제목·대표·팀원·첨부 확인, 필요한 조치를 14:00 전 완료'],
 ['7.4',30,'백업','제출본·접수 증빙 백업','A','제출 당시 파일·앱 버전·접수 확인 자료 보관'],
];
const days = [
 [24,'목','앱 점검, 실제 데이터·API 연결 확인','지역 분석 기준·장소 조사·외부 평가 일정·공모 규격 확인','필수 범위와 보완 목록 확정'],
 [25,'금','조건 판정, 코스 생성·경로 계산 완성','실제 장소 규정·지역 선정 근거·평가 정답 확정','실제 데이터 검토본과 핵심 추천 기능 준비'],
 [26,'토','전체 통합·평가 환경 고정, 첫 기술평가 오류 수정','고정 기술평가, 사용자 과제 리허설·참여 일정 확인','첫 기술평가 결과 보존, 다음 날 사용자 평가 준비'],
 [27,'일','오류 수정·회귀 점검, 최종 앱 안정화·시연 제작','외부 과제 진행, 성과 수치·한계·원자료 확정','앱·시연·성과 원자료 최종 고정'],
 [28,'월','구현 구조·기능·시연 설명자료, 본문 통합 검토','지역 선정·데이터 활용·성과검증 보고서, 본문 초안','활용사례 본문과 증빙 설명 초안 완성'],
 [29,'화','증빙 ZIP·백업 정리, 최종 교차 검수','서식4 편집, 신청서류·서명·PDF 완성','제출 PDF·참고자료 ZIP 최종 완료'],
 [30,'수','파일·접속 점검, 접수 확인·백업','11시까지 온라인 제출, 접수 확인·오류 대응','공식 마감 14시 전 접수 완료 확인'],
];
const wb=Workbook.create();
const ws=wb.worksheets.add('상세 WBS');
const daily=wb.worksheets.add('일별 역할 배분');
const dark='#243B53', ink='#102A43', muted='#52606D', pale='#F0F4F8';
function base(s,lastRow,lastCol){
 s.showGridLines=false;
 s.getRange(`A1:${lastCol}${lastRow}`).format.font={name:'Malgun Gothic',size:11,color:ink};
 s.getRange(`A1:${lastCol}${lastRow}`).format.verticalAlignment='center';
 s.getRange(`A1:${lastCol}${lastRow}`).format.rowHeight=26;
 s.getRange('A2').format.font={name:'Malgun Gothic',size:16,bold:true,color:dark};
 s.getRange(`A2:${lastCol}2`).format.rowHeight=32;
 s.tabColor=dark;
}
base(ws,7+tasks.length,'I');
ws.getRange('A2').values=[['우리 개와 끝까지 함께 — 2인 WBS']];
ws.getRange('A3').values=[['2026.09.24~09.30  |  9/27 앱·시연 완료 · 9/28~29 제출자료 제작 · 9/30 제출']];
ws.getRange('A3:I3').format.font={size:11,color:muted};
ws.getRange('A5').values=[['전체 작업']]; ws.getRange('B5').formulas=[[`=COUNTA(A8:A${7+tasks.length})`]];
ws.getRange('C5').values=[['완료 작업']];ws.getRange('D5').formulas=[[`=COUNTIFS(G8:G${7+tasks.length},"완료")`]];
ws.getRange('E5').values=[['완료율']];ws.getRange('F5').formulas=[['=D5/B5']];ws.getRange('F5').setNumberFormat('0%');
ws.getRange('G5').values=[['상태·완료일·메모 입력']];
ws.getRange('A7:I7').values=[['WBS','마감일','분류','작업','담당','완료 기준·산출물','상태','실제 완료일','메모·증빙 위치']];
const end=7+tasks.length;
ws.getRange(`A8:I${end}`).values=tasks.map(t=>[t[0],new Date(Date.UTC(2026,8,t[1])),t[2],t[3],t[4],t[5],'미착수',null,null]);
const widths=[9,13,15,43,22,72,14,15,32];
widths.forEach((v,i)=>ws.getRange(`${String.fromCharCode(65+i)}1:${String.fromCharCode(65+i)}${end}`).format.columnWidth=v);
ws.getRange(`A8:I${end}`).format.rowHeight=59;
ws.getRange(`C8:I${end}`).format.wrapText=true;
ws.getRange(`B8:B${end}`).setNumberFormat('mm/dd');ws.getRange(`H8:H${end}`).setNumberFormat('mm/dd');
ws.getRange(`G8:I${end}`).format.fill='#FFF8DF';
ws.getRange(`G8:G${end}`).dataValidation={rule:{type:'list',values:['미착수','진행중','검토중','완료','보류']}};
ws.getRange(`G8:G${end}`).conditionalFormats.add('containsText',{text:'완료',format:{fill:'#DCEFE5',font:{color:'#145A32'}}});
ws.getRange(`G8:G${end}`).conditionalFormats.add('containsText',{text:'보류',format:{fill:'#FBE2E2',font:{color:'#A4262C'}}});
ws.getRange(`G8:G${end}`).conditionalFormats.add('containsText',{text:'진행중',format:{fill:'#DFECFA',font:{color:'#1E4E79'}}});
const table=ws.tables.add(`A7:I${end}`,true,'WBSTasks');table.showFilterButton=true;
ws.getRange('A7:I7').format={fill:dark,font:{name:'Malgun Gothic',size:11,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:32};
tasks.forEach((t,i)=>{if(i===0||t[1]!==tasks[i-1][1])ws.getRange(`A${8+i}:I${8+i}`).format.borders={top:{style:'medium',color:'#BCCCDC'}}; if(t[2]==='마일스톤')ws.getRange(`A${8+i}:F${8+i}`).format.fill='#E3EDF7';});
ws.freezePanes.freezeRows(7);ws.freezePanes.freezeColumns(2);

base(daily,33,'H');
daily.getRange('A2').values=[['9월 24~30일 역할 배분']];
daily.getRange('A3').values=[['A: 개발·배포·기술 증빙   B: 데이터·성과검증·제출 서류   공동: 의사결정·교차 검수']];
daily.getRange('A5').values=[['앱·시연 완료']];daily.getRange('B5').values=[[new Date(Date.UTC(2026,8,27))]];daily.getRange('B5').setNumberFormat('mm/dd');
daily.getRange('C5').values=[['제출자료: 9/28(월)~9/29(화)']];daily.getRange('E5').values=[['제출 목표 9/30 11시 · 공식 마감 14시(KST)']];
daily.getRange('A7:H7').values=[['날짜','요일','A — 개발 담당','B — 데이터·제출 담당','당일 완료 기준','작업 수','완료 수','완료율']];
daily.getRange('A8:H14').values=days.map(d=>[new Date(Date.UTC(2026,8,d[0])),d[1],d[2],d[3],d[4],null,null,null]);
daily.getRange('A8:A14').setNumberFormat('mm/dd');
for(let r=8;r<=14;r++){
 daily.getRange(`F${r}`).formulas=[[`=COUNTIFS('상세 WBS'!$B$8:$B$${end},A${r})`]];
 daily.getRange(`G${r}`).formulas=[[`=COUNTIFS('상세 WBS'!$B$8:$B$${end},A${r},'상세 WBS'!$G$8:$G$${end},"완료")`]];
 daily.getRange(`H${r}`).formulas=[[`=IF(F${r}=0,"",G${r}/F${r})`]];
}
daily.getRange('H8:H14').setNumberFormat('0%');
daily.getRange('A7:H7').format={fill:dark,font:{name:'Malgun Gothic',size:11,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:32};
daily.getRange('A8:H14').format.rowHeight=85;daily.getRange('C8:E14').format.wrapText=true;
daily.getRange('A11:H11').format.fill='#E3EDF7';daily.getRange('A12:H13').format.fill='#EDF3E9';
[13,8,46,52,46,11,11,12].forEach((v,i)=>daily.getRange(`${String.fromCharCode(65+i)}1:${String.fromCharCode(65+i)}33`).format.columnWidth=v);
daily.getRange('A17').values=[['운영 기준']];daily.getRange('A17').format.font={bold:true,color:dark};
const notes=[
 ['일정 고정','9/27까지 앱 안정화·시연 제작·성과 측정 종료. 9/28~29는 확정 자료로 제출물을 제작한다.'],
 ['평가 순서','9/26 평가 버전 고정 → 기술평가 → 9/27 외부 과제 → 수정·회귀 → 최종 시연·버전 고정. 첫 평가 결과를 보존한다.'],
 ['범위 조정','실제 장소 15곳 목표, 부족 시 검증 가능한 9곳 안팎으로 축소. 미확인 규정을 허용으로 처리하지 않는다.'],
 ['성과 표현','날짜 미지정 코스 추천과 실제 예약·현장 이용을 구분한다. 외부 참여자가 없으면 외부 사용성은 미검증으로 표시한다.'],
 ['연휴 대응','9/24~27 연휴·주말의 업체 회신 지연에 대비한다. 공개 자료로 우선 진행하고 회신 미확보 항목은 제외·미확인 처리한다.'],
 ['제출 규격','필수: 서식1-1·2·3·4 PDF. 서식1-1·2·3은 두 참가자 서명. 서식4는 2~3쪽·함초롱바탕 11pt·줄간격 160. 참고자료 ZIP.'],
 ['상태 입력','상세 WBS의 노란 칸에 상태·실제 완료일·메모를 입력한다. 모든 상태는 계획 기준 미착수이며, 완료 수와 완료율은 자동 집계된다.'],
];
notes.forEach((n,i)=>{const r=18+i;daily.getRange(`A${r}`).values=[[n[0]]];daily.getRange(`C${r}`).values=[[n[1]]];daily.getRange(`C${r}:H${r}`).merge();daily.getRange(`C${r}:H${r}`).format.wrapText=true;daily.getRange(`A${r}:H${r}`).format.rowHeight=40;});
daily.getRange('A27').values=[['참고자료']];daily.getRange('A27').format.font={bold:true,color:dark};
const sources=[
 ['공모요강','(첨부1) (공모요강) 2026 한국관광 데이터랩 활용 경진대회.pdf, 3·5·11~12쪽'],
 ['서비스 계획','https://app.notion.com/p/3da4a247b914813ca624e93797e6f346'],
 ['구현 가이드','https://app.notion.com/p/3e04a247b914812b8349e7052dd002b4'],
 ['일정 수정','사용자 요청: 9/27 최종 앱 안정화·시연 제작 완료, 월·화 제출자료 제작'],
 ['연휴 기준','한국천문연구원 2026년 월력요항: https://www.kasi.re.kr/kor/post/newsMaterial/32031'],
];
sources.forEach((n,i)=>{const r=28+i;daily.getRange(`A${r}`).values=[[n[0]]];daily.getRange(`C${r}`).values=[[n[1]]];daily.getRange(`C${r}:H${r}`).merge();daily.getRange(`C${r}:H${r}`).format.wrapText=true;daily.getRange(`A${r}:H${r}`).format.rowHeight=32;});

wb.recalculate();
if(ws.getRange('B5').values[0][0]!==tasks.length)throw Error('Task count mismatch');
// Verify linked progress responds to an editable task status, then restore the plan.
ws.getRange('G8').values=[['완료']];wb.recalculate();
if(ws.getRange('D5').values[0][0]!==1||daily.getRange('G8').values[0][0]!==1)throw Error('Status recalculation failed');
ws.getRange('G8').values=[['미착수']];wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'일별 역할 배분!F7:H14',include:'values,formulas',tableMaxRows:8,tableMaxCols:3,maxChars:2500})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1000})).ndjson);
await fs.mkdir(outputDir,{recursive:true});
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(`${outputDir}/우리개와끝까지함께_WBS_0924-0930.xlsx`);
for(const [sheetName,range,file] of [['상세 WBS','A7:G15','wbs-top.png'],['상세 WBS','A24:G29','wbs-deadline.png'],['일별 역할 배분','A2:H14','daily.png'],['일별 역할 배분','A17:H32','notes.png']]){
 const p=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(`${previewDir}/${file}`,new Uint8Array(await p.arrayBuffer()));
}
console.log(JSON.stringify({output:`${outputDir}/우리개와끝까지함께_WBS_0924-0930.xlsx`,tasks:tasks.length,days:days.length}));
