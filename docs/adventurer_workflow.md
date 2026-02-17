# 모험가 업무 흐름 추적 (현재 코드 기준)

이 문서는 `SimulationRuntime` 기준으로 모험가 1명을 따라가며 **업무 선택 순서**와 **탐색 선택 방식**을 정리한 노트입니다.

## 1) 하루 루틴에서 업무로 들어가는 시점

- 시뮬레이터는 매 틱(1분)마다 현재 시각을 계산합니다.
- 06/12/18시는 식사, 20시~익일 05시는 취침, 그 외 시간은 업무 시간입니다.
- 업무 시간이고 현재 액션의 남은 틱이 0 이하일 때 다음 업무를 다시 고릅니다.

즉 모험가도 우선은 일반 일과(식사/취침/업무) 게이트를 통과한 뒤, 업무 시간에만 고유 로직으로 들어갑니다.

## 2) 모험가 업무 선택 우선순위

업무 시간에서 모험가(`job == "모험가"`)는 다음 순서로 행동합니다.

1. **하루 1회 게시판 확인**
   - 당일 아직 게시판을 안 봤고 `게시판확인` 액션이 후보에 있으면 무조건 `게시판확인`을 먼저 선택합니다.
2. **길드 발행 이슈 조회**
   - 길드 디스패처가 자원 키별로 `탐색`/채집 액션을 발행합니다.
   - 모험가의 허용 액션 목록에 있는 것만 후보로 남깁니다.
   - 발행 `amount`만큼 후보 리스트에 중복 삽입해서, 랜덤 선택 시 사실상 가중치가 되게 합니다.
3. **후보가 비면 배회**
   - 수행할 업무가 없으면 `배회` 1틱으로 떨어집니다.
4. **최종 랜덤 선택**
   - 남은 후보 중 하나를 난수로 고르고, 액션별 설정된 지속 틱을 적용합니다.

## 3) 길드가 탐색/채집을 발행하는 방식

길드 디스패처는 리소스 키마다 아래를 비교합니다.

- `Available < TargetAvailable` 이면 `탐색` 발행
- `Stock < TargetStock` 이면 채집 발행
- 채집 발행량은 `Available`을 넘지 못함

또한 런타임에서는 `count_available_only_discovered=True`로 디스패처를 갱신하므로,
**발견되지 않은 자원은 가용량 0으로 계산**됩니다. 이 상태에서는 `탐색` 발행이 우선적으로 늘어납니다.

## 4) 실제 이동/행동 처리 방식

- 식사/취침은 해당 타일(식탁/침대)로 A* 경로 이동을 시도합니다.
- 업무 액션도 `action_required_entity`에 매핑된 엔티티가 있으면 그 타일로 이동합니다.
- 하지만 `탐색`, `게시판확인`처럼 작업 타일이 없으면, 마지막에 랜덤 인접 이동(혹은 제자리)으로 처리됩니다.

즉 현재 구현에서 모험가의 `탐색`은 **프런티어 기반 목적지 이동이 아니라 랜덤 워크에 가깝습니다.**

## 5) 프런티어 탐색 로직(별도 모듈)

별도 `exploration.py`에는 길드 보드 전역 상태 + NPC 증분 버퍼 모델이 있고,
다음 프런티어 선택은 `choose_next_frontier()`에서 랜덤 1개를 뽑습니다.

현재 `village_sim.py`에서는 `탐색` 액션일 때 `choose_next_frontier()`를 사용해
길드 보드의 프런티어 셀을 목표로 이동하도록 연동되어 있습니다.

## 6) 빠른 재현 예시 (엘린 1명 추적)

아래처럼 09시부터 틱을 진행하면,
- 먼저 `게시판확인` (1시간)
- 다음으로 `탐색` (1시간)
- 12시 식사
순으로 이어지는 것을 확인할 수 있습니다.

```bash
python - <<'PY'
from village_sim import SimulationRuntime, RenderNpc
from ldtk_integration import GameWorld, ResourceEntity

world=GameWorld(level_id='test',grid_size=16,width_px=160,height_px=160,entities=[
    ResourceEntity(key='herb_patch',name='약초밭',x=2,y=2,max_quantity=5,current_quantity=5,is_discovered=False),
    ResourceEntity(key='tree_oak',name='참나무',x=7,y=7,max_quantity=5,current_quantity=5,is_discovered=False),
],blocked_tiles=[])

npc=RenderNpc(name='엘린',job='모험가',x=0,y=0)
sim=SimulationRuntime(world,[npc],seed=3)
sim.ticks=9*sim.TICKS_PER_HOUR

prev=None
for _ in range(220):
    sim.tick_once()
    st=sim.state_by_name['엘린']
    if st.current_action != prev:
        print(sim.ticks, sim._current_hour(), st.current_action, st.ticks_remaining, (npc.x,npc.y))
        prev=st.current_action
PY
```

예시 출력:

- `541 9 게시판확인 59 ...`
- `601 10 탐색 59 ...`
- `721 12 식사 0 ...`

