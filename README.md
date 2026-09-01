# kongi-petfair-data

뽀시로그(콩이앱) 안 "콩이랑 뭐하지 → 펫페어 일정" 화면이 읽어가는 데이터 저장소.
케이펫페어 + 메가주 전시 일정을 주 1회 긁어서 `events.json` 하나로 만들어 둔다.
앱은 이 레포의 `events.json` 만 읽는다. GitHub Actions 가 매주 월요일 아침(KST)
`scrape_kpet.py` 를 돌려 갱신·커밋한다.

## 데이터 출처
케이펫페어 2026 전시일정 페이지 (메가주 일정도 이 목록에 함께 나옴):
https://k-pet.co.kr/information/exhibition-scheduled-all/

## 손으로 돌리는 법
```
pip install requests beautifulsoup4
python scrape_kpet.py
```

성공하면 `events.json` 과 `snapshots/latest.html` 이 갱신된다.
행사가 10건 미만이면 (사이트 리뉴얼 등) `events.json` 은 건드리지 않고
"수집 실패: N건" 을 남기고 exit 1 로 죽는다.
