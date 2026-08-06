# 남은 RTL 교육 과정

현재 완료: 1~10장  
남은 범위: 11~29장

---

# Part 3. 순차논리 심화

## 11장. `=`와 `<=` 심화

### 목표
- 블로킹·논블로킹 할당의 시뮬레이션 차이를 정확히 이해
- 여러 레지스터가 같은 에지에서 동시에 갱신되는 원리 이해
- race condition과 코드 순서 의존 문제 발견

### 핵심 내용
- active/NBA 영역의 직관적 설명
- `q1 = d; q2 = q1;`와 `q1 <= d; q2 <= q1;` 비교
- 조합 블록과 순차 블록의 할당 규칙
- 같은 신호에 여러 번 대입할 때 우선순위

### 실습
- 2단 파이프라인
- 두 레지스터 값 교환
- 잘못된 blocking sequential code 수정

---

## 12장. 카운터·타이머·분주기

### 목표
- 폭이 제한된 레지스터의 순환과 경계 이해
- terminal count를 이용해 주기 신호 생성

### 핵심 내용
- up/down counter
- modulo-N counter
- rollover
- saturation counter
- tick pulse
- clock divider와 clock enable 차이

### 실습
- N-cycle 주기 1클록 tick 생성기
- load/enable/clear 가능한 카운터

---

## 13장. 시프트 레지스터와 직렬·병렬 변환

### 핵심 내용
- logical shift와 register shift 차이
- SISO, SIPO, PISO, PIPO
- delay line
- 데이터와 valid 동시 지연

### 실습
- 8비트 serial-in parallel-out
- 파라미터화된 valid pipeline

---

## 14장. 리셋 설계

### 핵심 내용
- synchronous reset
- asynchronous reset
- active-high/active-low
- asynchronous assert, synchronous deassert 개념
- 모든 datapath register를 반드시 reset해야 하는지
- 초기 상태와 X propagation

### 실습
- reset synchronizer 구조 해석
- control register와 datapath register의 reset 정책 비교

---

## 15장. clock enable과 상태 유지

### 핵심 내용
- enable MUX가 플립플롭 입력에 생기는 구조
- `q <= q`가 불필요한 이유
- clear/set/load/enable 우선순위
- clock gating을 RTL에서 직접 만들 때의 위험

### 실습
- 우선순위가 있는 범용 레지스터
- valid sticky flag

---

# Part 4. 자료형·비트 정확도·재사용성

## 16장. signed/unsigned와 2의 보수

### 핵심 내용
- unsigned N비트 범위
- signed N비트 범위
- MSB와 부호 비트
- 음수의 2의 보수 표현
- signed 선언 위치
- 산술 오른쪽 시프트

### 실습
- signed 8비트 가감산기
- 음수 sign extension 확인

---

## 17장. 표현식 폭·오버플로·캐스팅

### 핵심 내용
- self-determined/context-determined expression
- 덧셈·곱셈 결과 폭
- truncation
- zero/sign extension
- `$signed`, `$unsigned`
- size cast와 type cast

### 실습
- 비트 정확한 MAC
- overflow flag
- saturation arithmetic

---

## 18장. `parameter`, `localparam`, `$clog2`

### 핵심 내용
- 재사용 가능한 모듈
- parameter override
- 계산 파라미터는 `localparam`
- 폭 계산
- 값 1일 때 `$clog2` 경계

### 실습
- DATA_W가 바뀌는 가산기
- DEPTH 기반 FIFO pointer 폭 계산

---

## 19장. packed/unpacked array와 메모리

### 핵심 내용
- packed vector
- unpacked array
- `logic [7:0] mem [0:255]`
- 다차원 배열
- 포트로 배열 전달
- inferred RAM의 기본 개념

### 실습
- register file
- single-port synchronous RAM

---

## 20장. `typedef`, `enum`, `struct`, `union`

### 핵심 내용
- 반복 자료형에 이름 부여
- enum state
- packed struct로 bus 묶기
- union의 동일 비트 해석
- 합성 가능한 사용 범위

### 실습
- 명령어 구조체
- enum 기반 상태 레지스터

---

# Part 5. 반복과 구조화

## 21장. 절차적 `for`

### 핵심 내용
- software loop와 hardware unrolling 차이
- 조합 블록의 반복 연산
- 순차 블록에서 배열 갱신
- loop variable
- 합성 가능한 반복 횟수

### 실습
- parity/XOR reduction 직접 구현
- 배열 전체 reset
- priority encoder

---

## 22장. `generate`와 `genvar`

### 핵심 내용
- elaboration 시 하드웨어 복제
- generate-for
- generate-if
- named generate block
- parameter에 따른 구조 변경

### 실습
- N비트 ripple-carry adder
- 선택 가능한 pipeline stage

---

## 23장. `function`, `task`, `package`, include 구조

### 핵심 내용
- RTL function의 조합논리적 의미
- task와 function 차이
- package로 type/constant/function 공유
- include guard
- 파일 컴파일 순서

### 실습
- saturation function
- package에 opcode와 공통 type 정리

---

# Part 6. FSM과 실전 RTL 패턴

## 24장. FSM 기본

### 핵심 내용
- state register
- next-state combinational logic
- output logic
- 상태 유지 기본값
- illegal state recovery

### 실습
- IDLE/RUN/DONE FSM
- 버튼 debounce FSM 개념

---

## 25장. Moore와 Mealy, FSM 코딩 스타일

### 핵심 내용
- Moore output
- Mealy output
- one-process/two-process/three-process
- latency와 glitch 차이
- enum과 unique case

### 실습
- sequence detector
- 요청/응답 controller

---

## 26장. valid/ready 핸드셰이크

### 핵심 내용
- transfer = valid && ready
- valid 유지 규칙
- ready와 backpressure
- payload 안정성
- skid buffer 개념
- combinational ready path의 위험

### 실습
- 1-entry output buffer
- random backpressure 대응 스트림 모듈

---

## 27장. FIFO

### 핵심 내용
- storage array
- write/read pointer
- count 방식과 extra-MSB 방식
- full/empty
- simultaneous read/write
- overflow/underflow 방지

### 실습
- parameterized synchronous FIFO
- boundary case 점검

---

## 28장. 파이프라인, latency, throughput

### 핵심 내용
- register stage
- critical path
- latency와 throughput 구분
- 데이터·valid·ID 정렬
- stallable pipeline 개념

### 실습
- 2단 산술 pipeline
- valid가 함께 이동하는 MAC pipeline

---

## 29장. 실전 통합 설계

### 목표
앞에서 배운 문법과 구조를 하나의 작은 IP로 통합합니다.

### 대상 구조

```text
APB register interface
→ configuration/status registers
→ streaming input
→ accumulator/MAC datapath
→ streaming output
→ interrupt/error status
```

### 설계 항목
- APB 주소 decoder
- read/write register
- vector length 설정
- valid/ready 입력
- 누산 및 마지막 샘플 검출
- output backpressure
- busy/done/irq/error
- 파라미터화된 폭

### 완료 기준
- lint 관점의 코드 점검
- latch와 multiple driver 없음
- 비트 폭 경고 없음
- reset 이후 상태 명확
- handshake 규칙 준수
- 모듈별 설계 설명 가능

---

# RTL 과정 종료 후 연결

RTL 29장을 마친 뒤 `Verification/` 과정에서 다음 순서로 이어갑니다.

```text
기본 SystemVerilog testbench
→ self-checking
→ assertion
→ functional coverage
→ class/OOP
→ constrained random
→ interface/clocking block
→ UVM
→ AMBA 기반 검증 프로젝트
```