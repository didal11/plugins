# Verilog/SystemVerilog RTL 교육 과정

## 과정 목표

이 과정의 목표는 문법을 암기하는 데서 끝나지 않고, 코드를 보았을 때 실제 조합회로·플립플롭·MUX·FSM·파이프라인 구조를 머릿속으로 그릴 수 있게 만드는 것입니다.

기준 범위는 **합성 가능한 RTL 설계**입니다. 객체지향 SystemVerilog, UVM, functional coverage 등 검증 전용 내용은 `Verification/` 과정에서 별도로 다룹니다.

## 현재 진행률

- 전체 계획: **29개 챕터**
- 완료: **1~10장**
- 다음 진도: **11장 `=`와 `<=` 심화**
- 진행률: **약 35%**

하루 3챕터 기준 이론 진도는 약 7일, 직접 코딩과 복습까지 포함하면 약 10~14일을 예상합니다.

---

## 전체 목차

### Part 1. 하드웨어 기술 언어의 관점 — 완료

1. HDL의 핵심 관점: 순차 실행이 아니라 동시 동작하는 회로
2. `module`: 하드웨어 블록, 포트, 인스턴스, 계층
3. `input`, `output`, `inout`: 모듈 경계와 신호 방향
4. `wire`, `logic`, `reg`: 연결망, 변수, 저장회로 오해 바로잡기
5. 비트 폭과 숫자 표현: `[7:0]`, 리터럴, 연결·복제
6. 연산자: 비트·논리·축약·비교·시프트 연산

### Part 2. 조합논리와 순차논리의 기본 — 완료

7. `assign`: 연속 할당과 조합회로
8. `always_comb`: 절차적 조합논리와 래치 방지
9. `case`: MUX, decoder, 주소 디코딩, `casez/casex`
10. `always_ff`: 클록, 플립플롭, 리셋, enable, 파이프라인

### Part 3. 순차논리 심화 — 예정

11. `=`와 `<=` 심화 및 시뮬레이션 스케줄링
12. 카운터, 타이머, 분주기, rollover와 saturation
13. 시프트 레지스터, 직렬·병렬 변환, 지연선
14. 리셋 설계: 동기/비동기, assertion/deassertion, reset value
15. clock enable과 상태 유지, 우선순위 제어

### Part 4. 자료형·비트 정확도·재사용성 — 예정

16. signed/unsigned, 2의 보수, 부호 확장
17. 표현식 폭, 오버플로, truncation, casting
18. `parameter`, `localparam`, `$clog2`
19. packed/unpacked array와 메모리 표현
20. `typedef`, `enum`, `struct`, `union`

### Part 5. 반복과 구조화 — 예정

21. 절차적 `for`와 조합·순차 반복회로
22. `generate`, genvar, 파라미터 기반 하드웨어 생성
23. `function`, `task`, `package`, include 구조

### Part 6. FSM과 실전 RTL 패턴 — 예정

24. FSM 기본: state register와 next-state logic
25. Moore/Mealy, one/two/three-process FSM
26. valid/ready 핸드셰이크와 backpressure
27. FIFO, read/write pointer, full/empty 경계
28. 파이프라인, latency, throughput, 데이터와 제어 정렬
29. 실전 통합 설계: APB 제어 + 스트림 datapath + 상태/오류 처리

---

## 파일 구성

```text
RTL/
├── README.md
├── CURRENT_LESSONS.md       # 현재까지 완료한 1~10장 정리
├── FUTURE_CURRICULUM.md     # 11~29장 상세 진행 계획
└── examples/
    └── rtl_basics.sv        # 현재 진도 기반 예제 코드
```

## 학습 원칙

- 선언문 이름만 보고 회로를 판단하지 않습니다.
- 모든 코드에서 driver와 저장 여부를 확인합니다.
- 조합논리는 모든 입력 경우에 출력이 정해져야 합니다.
- 순차논리는 클록 직전 값과 클록 이후 값을 구분합니다.
- 비트 폭과 signed 여부를 항상 확인합니다.
- 문법을 배울 때마다 합성 결과 회로를 함께 그립니다.
