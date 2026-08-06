# 현재까지 완료한 RTL 교육 내용

완료 범위: 1~10장  
전체 RTL 과정 기준 진행률: 약 35%

---

# 1장. HDL의 핵심 관점

## 핵심 개념

C/C++ 프로그램의 문장은 대체로 실행 순서를 표현하지만, Verilog/SystemVerilog의 RTL 코드는 회로의 연결과 동작을 표현합니다.

```systemverilog
assign x = a & b;
assign y = x | c;
```

위 코드는 첫 줄이 끝난 뒤 둘째 줄이 실행되는 프로그램이 아니라 AND 게이트와 OR 게이트가 동시에 존재하는 회로입니다.

```text
a ──┐
    AND ── x ──┐
b ──┘          OR ── y
c ─────────────┘
```

## 반드시 기억할 것

- RTL은 계산 절차보다 하드웨어 구조를 설명합니다.
- 서로 다른 `assign`과 `always` 블록은 동시에 존재합니다.
- 블록 내부의 절차적 문장은 위에서 아래로 평가됩니다.
- 코드 줄 수와 하드웨어 동작 시간은 같은 개념이 아닙니다.

---

# 2장. `module`

`module`은 입출력 경계를 가진 하드웨어 블록입니다.

```systemverilog
module and_gate (
    input  logic a,
    input  logic b,
    output logic y
);
    assign y = a & b;
endmodule
```

모듈 정의는 설계도이고 인스턴스는 실제 배치된 하드웨어입니다.

```systemverilog
and_gate u_and_gate (
    .a(a_in),
    .b(b_in),
    .y(y_out)
);
```

- `and_gate`: 모듈 이름
- `u_and_gate`: 인스턴스 이름
- `.a(a_in)`: 하위 모듈의 `a` 포트에 상위 신호 `a_in` 연결

모듈을 계층적으로 조립하여 top module을 만듭니다.

---

# 3장. `input`, `output`, `inout`

포트 방향은 항상 **현재 모듈 기준**입니다.

- `input`: 외부가 구동하고 현재 모듈이 읽음
- `output`: 현재 모듈이 구동하고 외부가 읽음
- `inout`: 양쪽이 번갈아 구동할 수 있는 공유 선

```systemverilog
module gpio (
    input  logic out_enable,
    input  logic out_data,
    output logic in_data,
    inout  wire  pad
);
    assign pad     = out_enable ? out_data : 1'bz;
    assign in_data = pad;
endmodule
```

내부 RTL에서는 양방향 의미를 다음 세 신호로 나누는 편이 안전합니다.

```text
data_in

data_out

data_output_enable
```

---

# 4장. `wire`, `logic`, `reg`

## `wire`

외부 드라이버가 값을 결정하는 net, 즉 연결망입니다.

```systemverilog
wire y;
assign y = a & b;
```

## `reg`

기존 Verilog에서 절차적 블록 안에서 대입하기 위한 변수형입니다. 이름과 달리 반드시 플립플롭을 뜻하지 않습니다.

```verilog
reg y;
always @(*) begin
    y = a & b;
end
```

위 `y`는 조합회로 출력입니다.

## `logic`

SystemVerilog에서 일반적인 단일 드라이버 RTL 신호에 널리 사용하는 자료형입니다.

```systemverilog
logic y;
```

자료형 자체가 회로를 결정하지 않습니다.

```systemverilog
always_comb y = a & b;      // 조합회로
always_ff @(posedge clk) q <= d; // 플립플롭
```

## 핵심 규칙

- `wire`는 연결망입니다.
- `reg`라고 해서 반드시 register가 아닙니다.
- `logic`이라고 해서 저장소가 생기지 않습니다.
- 회로 종류는 대입 방식과 이벤트 조건이 결정합니다.

---

# 5장. 비트 폭과 숫자 표현

```systemverilog
logic       enable;    // 1비트
logic [7:0] data;      // 8비트
logic [31:0] address;  // 32비트
```

`[7:0]`의 비트 수는 `7 - 0 + 1 = 8`입니다.

## 숫자 리터럴

```systemverilog
1'b0
4'b1010
8'd25
8'hA5
16'hABCD
```

형식은 다음과 같습니다.

```text
비트수'진법값
```

## 비트 선택과 부분 선택

```systemverilog
data[0]    // 한 비트
data[7:4]  // 상위 4비트
```

## 연결과 복제

```systemverilog
assign data = {upper, lower};
assign zero_vector = {8{1'b0}};
```

## 폭 불일치

- 작은 값을 큰 신호에 넣으면 확장됩니다.
- 큰 값을 작은 신호에 넣으면 상위 비트가 잘립니다.
- 산술 결과를 보존하려면 연산 전에 피연산자를 확장해야 할 수 있습니다.

```systemverilog
logic [7:0] a, b;
logic [8:0] sum;

assign sum = {1'b0, a} + {1'b0, b};
```

인덱스와 개수는 필요한 폭이 다를 수 있습니다.

```text
8개 데이터의 인덱스: 0~7 → 3비트
데이터 개수 8 자체         → 4비트
```

---

# 6장. 연산자

## 비트 연산

```systemverilog
& | ^ ~
```

각 위치의 비트를 따로 계산합니다.

```text
1100 & 1010 = 1000
```

## 논리 연산

```systemverilog
&& || !
```

벡터 전체를 0 또는 0이 아닌 값으로 판단하고 1비트 결과를 만듭니다.

```text
4'b1100 && 4'b1010 = 1'b1
```

## 축약 연산

```systemverilog
&a   // 모든 비트가 1인가
|a   // 하나라도 1인가
^a   // parity
```

## 비교

```systemverilog
==  !=   // 일반적인 값 비교
=== !==  // X와 Z까지 정확히 비교, 주로 테스트벤치
```

## 시프트

```systemverilog
<< >> <<< >>>
```

시프트 결과 폭은 자동으로 늘어나지 않습니다.

## 조건 연산자

```systemverilog
assign y = sel ? b : a;
```

2:1 MUX를 표현합니다.

---

# 7장. `assign`

`assign`은 한 번 실행되는 복사가 아니라 오른쪽 식의 결과가 왼쪽 신호를 계속 구동하도록 연결하는 연속 할당입니다.

```systemverilog
assign y = a & b;
```

오른쪽 입력이 변하면 출력도 따라 변합니다.

```systemverilog
assign transfer = valid && ready;
assign full     = (count == MAX_COUNT);
assign y        = sel ? b : a;
```

## 주의사항

- 여러 `assign` 문은 동시에 존재합니다.
- 하나의 신호를 여러 `assign` 문에서 구동하지 않습니다.
- `assign`과 `always_comb`이 같은 신호를 함께 구동하지 않습니다.
- 자기 자신으로 돌아오는 조합 루프를 만들지 않습니다.

```systemverilog
assign a = ~a; // 잘못된 조합 루프
```

---

# 8장. `always_comb`

조건이 많은 조합논리를 절차적 문법으로 표현합니다.

```systemverilog
always_comb begin
    if (sel)
        y = b;
    else
        y = a;
end
```

위 코드는 MUX입니다.

## 래치 방지

조합논리에서는 모든 입력 경우에 모든 출력이 결정되어야 합니다.

잘못된 예:

```systemverilog
always_comb begin
    if (enable)
        y = a;
end
```

`enable = 0`일 때 새 값이 없으므로 이전 값을 유지해야 하고 래치가 필요해집니다.

수정 방법:

```systemverilog
always_comb begin
    y = 1'b0;

    if (enable)
        y = a;
end
```

## 기본 규칙

- `always_comb`에서는 보통 블로킹 할당 `=` 사용
- 출력 기본값을 블록 위쪽에 배치
- 한 출력은 한 블록이 담당
- 내부 문장의 데이터 의존 순서를 지킴

---

# 9장. `case`

하나의 선택 신호 값을 여러 상수와 비교할 때 사용합니다.

```systemverilog
always_comb begin
    case (opcode)
        2'd0: result = a + b;
        2'd1: result = a - b;
        2'd2: result = a & b;
        default: result = a | b;
    endcase
end
```

이는 여러 입력 중 하나를 고르는 MUX와 비교기를 만듭니다.

## `default`

처리되지 않은 값에서 출력 대입이 빠지지 않도록 합니다.

## `casez`

`?` 또는 Z 위치를 wildcard로 사용해 일부 비트를 무시할 수 있습니다.

```systemverilog
casez (request)
    4'b1???: grant = 2'd3;
    4'b01??: grant = 2'd2;
    4'b001?: grant = 2'd1;
    default: grant = 2'd0;
endcase
```

## `casex`

X까지 wildcard로 무시하여 초기화 오류를 숨길 수 있으므로 일반 RTL에서는 피하는 것이 안전합니다.

## 실전 사용

- opcode decoder
- APB 주소 decoder
- FSM state 선택
- priority encoder

---

# 10장. `always_ff`, 클록과 플립플롭

```systemverilog
always_ff @(posedge clk) begin
    q <= d;
end
```

클록이 0에서 1로 바뀌는 순간의 `d`를 저장하고 다음 클록까지 유지합니다.

## 논블로킹 할당

```systemverilog
always_ff @(posedge clk) begin
    q1 <= d;
    q2 <= q1;
end
```

같은 에지에서 다음과 같이 갱신됩니다.

```text
새 q1 = 기존 d
새 q2 = 기존 q1
```

따라서 데이터가 한 단계씩 이동하는 파이프라인이 됩니다.

## enable

```systemverilog
always_ff @(posedge clk) begin
    if (enable)
        q <= d;
end
```

`enable = 0`일 때 대입하지 않는 것은 기존 플립플롭 값을 유지하는 정상적인 동작입니다.

## 동기 리셋

```systemverilog
always_ff @(posedge clk) begin
    if (reset)
        q <= '0;
    else
        q <= d;
end
```

클록 상승 에지에서 리셋이 적용됩니다.

## 비동기 active-low 리셋

```systemverilog
always_ff @(posedge clk or negedge reset_n) begin
    if (!reset_n)
        q <= '0;
    else
        q <= d;
end
```

`reset_n`이 1에서 0으로 내려가면 클록을 기다리지 않고 리셋합니다.

## 현재값과 다음값

```systemverilog
count <= count + 1'b1;
```

다음과 같이 읽습니다.

```text
다음 count = 현재 count + 1
```

## 핵심 코딩 규칙

```text
always_comb → =
always_ff   → <=
```

한 레지스터는 하나의 `always_ff` 블록에서 관리합니다.

---

# 현재 체크포인트

현재까지 다음을 할 수 있어야 합니다.

- 간단한 모듈의 입출력과 계층 구조 읽기
- `wire`, `logic`, `reg`를 보고 잘못된 저장소 판단을 하지 않기
- 비트 폭과 리터럴 해석
- `assign`으로 기본 조합회로 작성
- `always_comb`에서 MUX와 decoder 작성
- 대입 누락에 따른 래치 위험 발견
- `always_ff`에서 플립플롭, enable, reset, pipeline 해석
- `valid && ready` 핸드셰이크 조건 이해

다음 장에서는 `=`와 `<=`가 시뮬레이터의 이벤트 스케줄 안에서 어떻게 다르게 반영되는지 더 깊게 다룹니다.