# 반도체 설계·검증 교육 자료

이 디렉터리는 다음 학습 흐름을 하나의 교육 과정으로 관리합니다.

1. **C / C++**: RTL 설계 주변 도구, 임베디드 펌웨어, DV/UVM 연계에 필요한 프로그래밍 기반
2. **RTL**: Verilog/SystemVerilog를 사용한 조합논리·순차논리·FSM·파라미터화 설계
3. **Verification**: RTL과 C/C++ 과정을 마친 뒤 진행할 SystemVerilog 검증 및 UVM 과정

## 디렉터리

```text
education/
├── C_CPP/          # C와 C++ 통합 교육
├── RTL/            # Verilog/SystemVerilog RTL 교육
└── Verification/   # 추후 검증 교육용 빈 디렉터리
```

## 전체 학습 순서

```text
C 기초 및 메모리 모델
→ C++ 객체지향 및 자료구조
→ Verilog/SystemVerilog RTL
→ 테스트벤치와 Assertion
→ 객체지향 SystemVerilog
→ UVM
→ AMBA 기반 설계 검증
```

현재 RTL 과정은 29개 챕터 기준 **10개 챕터 완료, 약 35% 진행** 상태입니다.
