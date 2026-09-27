// 1. 반려견 조건 판정 보완 (WBS 2.1)
function checkPetCondition(petWeight, petCount) {

    console.log(`입력된 반려견 체중: ${petWeight}kg, 마릿수: ${petCount}마리`);
    
    let isAllowed = true;
    let failReason = "";

    
    if (petWeight >= 15) {
        isAllowed = false;
        failReason = "대형견(15kg 이상) 입장 제한";
    }

  
    if (petCount >= 3) {
        isAllowed = false;
        failReason = "최대 2마리까지만 동반 가능";
    }

    return { 통과여부: isAllowed, 사유: failReason };
}


function calculateCourse(isOvernight, startLocation, endLocation) {
    
    console.log(`일정: ${isOvernight ? '1박 2일' : '당일치기'}`);
    console.log(`출발지: ${startLocation} -> 종료지: ${endLocation}`);

    let coursePlan = [];

    if (isOvernight) {
        
        coursePlan = ["출발", "추천 식당", "추천 숙소", "추천 관광지", "종료"];
    } else {
       
        coursePlan = ["출발", "추천 관광지", "추천 카페", "종료"];
    }

    
    if (coursePlan.length === 0) {
        return "조건에 맞는 추천 장소가 부족합니다. 검색 조건을 넓혀주세요.";
    }

    return coursePlan;
}

console.log(checkPetCondition(12, 1));
console.log(calculateCourse(false, "서울", "가평"));
git config user.name "silbeolein"
git config user.email "eunbi433@gmail.com"