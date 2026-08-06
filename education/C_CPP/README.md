# C / C++ 통합 교육 과정

## 교육 목적

이 과정은 일반적인 문법 암기 과정이 아니라 다음 네 분야를 함께 고려합니다.

- RTL 설계 주변의 모델링·자동화 도구
- 임베디드 펌웨어와 메모리 맵 제어
- DV/UVM 환경의 C/C++ 연동과 참조 모델
- 시스템 수준에서 하드웨어와 소프트웨어의 경계를 이해하는 능력

C와 C++를 서로 분리된 언어로만 배우지 않고, C의 메모리·비트·컴파일 모델을 먼저 이해한 뒤 C++의 추상화와 객체지향으로 확장합니다.

---

## Part 0. 시작 준비

### 01. 프로그램이 만들어지는 전체 흐름
- 소스 코드, 전처리, 컴파일, 어셈블, 링크
- 실행 파일과 라이브러리
- 컴파일 오류와 링크 오류의 차이
- GCC/G++ 기본 사용

### 02. 하드웨어 분야에서 C/C++가 쓰이는 위치
- 임베디드 펌웨어
- 레지스터 모델과 메모리 맵
- RTL 참조 모델
- DPI-C
- SystemC/TLM 개념
- 테스트 데이터 생성 및 로그 분석

---

## Part 1. C 핵심 문법

### 03. 변수, 자료형, 표현 범위
- 정수형과 부동소수점형
- signed/unsigned
- 고정 폭 정수형 `uint8_t`, `int32_t`
- 오버플로와 변환

### 04. 연산자와 비트 연산
- 산술·비교·논리 연산
- `&`, `|`, `^`, `~`, `<<`, `>>`
- 비트 마스크
- 레지스터 필드 설정·해제·검사

### 05. 조건문과 반복문
- `if`, `switch`
- `for`, `while`, `do-while`
- 상태와 조건을 구조적으로 읽는 방법

### 06. 함수와 스코프
- 선언과 정의
- 매개변수와 반환값
- 값 전달
- 지역·전역 변수
- 헤더 파일 분리

### 07. 배열과 문자열
- 연속된 메모리
- 배열 인덱스
- 문자열의 널 문자
- 버퍼 크기와 경계 오류

### 08. 포인터 기초
- 주소와 역참조
- 포인터와 배열 관계
- 포인터 연산
- null pointer
- 다중 포인터

### 09. 구조체, 열거형, 공용체
- `struct`
- `enum`
- `union`
- 하드웨어 레지스터와 패킷 형식 표현
- 정렬과 padding

### 10. 저장 영역과 수명
- stack, heap, static storage
- 자동 변수와 정적 변수
- `static`, `extern`
- 함수 호출과 스택 프레임

### 11. 동적 메모리
- `malloc`, `calloc`, `realloc`, `free`
- 메모리 누수
- dangling pointer
- double free
- 소유권을 명확히 하는 습관

### 12. `const`, `volatile`, `restrict`
- 읽기 전용 의도
- 메모리 맵 레지스터와 `volatile`
- 컴파일러 최적화와 실제 메모리 접근
- ISR/하드웨어 공유 값 주의점

### 13. 전처리기와 빌드 구조
- `#include`, `#define`
- include guard
- 조건부 컴파일
- 매크로의 위험성
- 여러 소스 파일 링크

### 14. 파일 입출력과 데이터 처리
- 바이너리·텍스트 파일
- CSV/로그 처리
- 테스트 벡터 읽기와 결과 저장

### 15. 디버깅과 오류 처리
- 경고 옵션
- assert
- 반환 코드
- GDB 기본
- sanitizer 개념

---

## Part 2. 임베디드·RTL 연계 C

### 16. 메모리 맵 I/O
- 주소에 의미를 부여하는 방법
- 레지스터 read/write
- bit field와 mask
- read-modify-write

### 17. 인터럽트와 동시성 기초
- ISR의 역할
- 공유 변수
- atomicity 개념
- polling과 interrupt 비교

### 18. 하드웨어 드라이버 구조
- 초기화
- 설정
- 상태 확인
- 오류 처리
- timeout

### 19. 고정소수점과 비트 정확도
- 정수 기반 실수 표현
- scale과 saturation
- RTL 결과와 C 참조 모델 비교

### 20. C 참조 모델
- 입력 벡터 처리
- golden result 생성
- RTL과 동일한 폭·부호·오버플로 재현

---

## Part 3. C++ 핵심

### 21. C++의 추가 개념
- namespace
- reference
- function overloading
- default argument
- `auto`의 제한적 사용

### 22. 클래스와 객체
- 데이터와 동작 묶기
- 접근 지정자
- 멤버 함수
- 객체의 수명

### 23. 생성자와 소멸자
- 초기화 목록
- 복사 생성
- 이동 의미론 입문
- RAII

### 24. 캡슐화와 인터페이스
- 내부 구현 숨기기
- 불변조건
- getter/setter 남용 피하기
- 하드웨어 모델 객체 설계

### 25. 상속과 다형성
- base/derived class
- virtual function
- abstract class
- 검증 컴포넌트 구조와 연결

### 26. 연산자 오버로딩
- 값 객체
- 비트 벡터·트랜잭션 비교
- 과도한 오버로딩의 위험

### 27. 템플릿
- 함수 템플릿
- 클래스 템플릿
- 자료형 독립적인 FIFO·scoreboard 구조

### 28. STL 핵심
- `vector`, `array`, `deque`
- `map`, `unordered_map`
- `string`
- iterator와 algorithm

### 29. 스마트 포인터와 소유권
- `unique_ptr`
- `shared_ptr`
- `weak_ptr`
- raw pointer가 필요한 경우

### 30. 예외와 오류 처리
- exception의 장단점
- 임베디드 환경의 제한
- 결과 타입과 상태 코드

---

## Part 4. 검증 연계 C++

### 31. 트랜잭션 객체 설계
- packet/command/result 클래스
- 비교·출력·직렬화
- 유효성 검사

### 32. 참조 모델과 scoreboard
- 입력 큐
- 예상 결과 생성
- 실제 결과 매칭
- 순서 보존과 ID 기반 비교

### 33. 랜덤 테스트 데이터
- 난수 엔진
- 분포
- seed 재현성
- 유효·비유효 입력 생성

### 34. DPI-C 개념
- SystemVerilog에서 C 함수 호출
- C에서 SystemVerilog 함수 호출
- 자료형 경계
- 2-state/4-state 데이터 주의점

### 35. SystemC/TLM 입문
- 모듈과 프로세스
- 시간 모델
- transaction-level modeling
- RTL보다 상위 수준의 모델링

---

## 권장 실습

1. 32비트 메모리 맵 레지스터 조작기
2. UART 패킷 parser
3. 고정소수점 MAC C 참조 모델
4. FIFO 자료구조
5. C++ transaction 및 scoreboard
6. RTL 결과 CSV 비교 도구

## 진행 상태

이 폴더는 기존 C/C++ 교육 계획을 하나로 통합한 기준 문서입니다. 세부 챕터별 본문과 실습 코드는 교육 진행에 맞춰 추가합니다.
