import density
import movement
import behavior_analysis
import risk_predictor

dens_an = density.DensityAnalyzer()
move_an = movement.MovementAnalyzer()
behv_an = behavior_analysis.BehaviorAnalyzer()
risk_pr = risk_predictor.RiskPredictor()

print("=================================================================")
print("RUNNING VISIONGUARD DYNAMIC REAL-TIME RISK VALIDATION SUITE")
print("=================================================================")

# Scenario 1: Single person sitting/standing normally
print("\n--- SCENARIO 1: 1 Person Sitting/Standing Normally ---")
det1 = [{'box': (100, 100, 300, 400), 'area': 60000, 'class_id': 0}]
d1 = dens_an.analyze(det1, 640, 480)
m1 = {'speed': 0.5, 'turbulence': 0.2, 'acceleration': 0.0, 'score': 5.0, 'is_panic': False, 'level': 'LOW'}
b1 = behv_an.analyze(d1, m1)
r1 = risk_pr.predict(d1, m1, b1, people_count=1)
print(f"Count: {r1['person_count']}, Density: {d1['density_score']}%, Risk: {r1['score']}%, Level: {r1['level']}")
assert r1['level'] == 'SAFE', f"Expected SAFE but got {r1['level']}"
print("[PASS] 1 person standing or moving normally stays strictly SAFE.")

# Scenario 2: 3 People with normal movement
print("\n--- SCENARIO 2: 3 People Moving Normally ---")
det2 = [
    {'box': (50, 100, 150, 300), 'area': 20000, 'class_id': 0},
    {'box': (200, 100, 300, 300), 'area': 20000, 'class_id': 0},
    {'box': (350, 100, 450, 300), 'area': 20000, 'class_id': 0}
]
d2 = dens_an.analyze(det2, 640, 480)
m2 = {'speed': 2.2, 'turbulence': 0.8, 'acceleration': 0.1, 'score': 16.0, 'is_panic': False, 'level': 'LOW'}
b2 = behv_an.analyze(d2, m2)
r2 = risk_pr.predict(d2, m2, b2, people_count=3)
print(f"Count: {r2['person_count']}, Density: {d2['density_score']}%, Risk: {r2['score']}%, Level: {r2['level']}")
assert r2['level'] in ('SAFE', 'CAUTION'), f"Expected SAFE or CAUTION but got {r2['level']}"
print("[PASS] Small group with normal movement stays SAFE/CAUTION.")

# Scenario 3: Large crowd (15 people) with calm, orderly movement
print("\n--- SCENARIO 3: Large Crowd (15 People) with Calm Movement ---")
det3 = [{'box': (i*40, 100, i*40+35, 300), 'area': 7000, 'class_id': 0} for i in range(15)]
d3 = dens_an.analyze(det3, 640, 480)
m3 = {'speed': 1.6, 'turbulence': 0.6, 'acceleration': 0.0, 'score': 12.0, 'is_panic': False, 'level': 'LOW'}
b3 = behv_an.analyze(d3, m3)
for _ in range(8):
    r3 = risk_pr.predict(d3, m3, b3, people_count=15)
print(f"Count: {r3['person_count']}, Density: {d3['density_score']}%, Risk: {r3['score']}%, Level: {r3['level']}")
assert r3['level'] in ('SAFE', 'CAUTION'), f"Expected SAFE or CAUTION (low/moderate) but got {r3['level']}"
print("[PASS] Large orderly crowd remains moderate without triggering false High Risk.")

# Scenario 3B: Moderate crowd (8 people) with active movement
print("\n--- SCENARIO 3B: Moderate Crowd (8 People) with Active Flow ---")
det3b = [{'box': (i*70, 100, i*70+50, 300), 'area': 10000, 'class_id': 0} for i in range(8)]
d3b = dens_an.analyze(det3b, 640, 480)
m3b = {'speed': 4.5, 'turbulence': 2.8, 'acceleration': 0.8, 'score': 38.0, 'is_panic': False, 'level': 'MEDIUM'}
b3b = behv_an.analyze(d3b, m3b)
for _ in range(8):
    r3b = risk_pr.predict(d3b, m3b, b3b, people_count=8)
print(f"Count: {r3b['person_count']}, Density: {d3b['density_score']}%, Risk: {r3b['score']}%, Level: {r3b['level']}")
assert r3b['level'] in ('SAFE', 'CAUTION'), f"Expected SAFE or CAUTION but got {r3b['level']}"
print("[PASS] Moderate crowd with active movement lands appropriately in SAFE/CAUTION.")
print("\n--- SCENARIO 4: Dense Crowd + Congestion + Abnormal Movement ---")
det4 = [{'box': (i*30, 80, i*30+40, 320), 'area': 9600, 'class_id': 0} for i in range(20)]
d4 = dens_an.analyze(det4, 640, 480)
m4 = {'speed': 8.5, 'turbulence': 6.5, 'acceleration': 2.8, 'score': 68.0, 'is_panic': False, 'level': 'HIGH'}
for _ in range(35):
    b4 = behv_an.analyze(d4, m4)
for _ in range(10):
    r4 = risk_pr.predict(d4, m4, b4, people_count=20)
print(f"Count: {r4['person_count']}, Density: {d4['density_score']}%, Congestion: {r4['breakdown']['congestion_score']}%, Risk: {r4['score']}%, Level: {r4['level']}")
assert r4['level'] in ('HIGH RISK', 'CRITICAL'), f"Expected HIGH RISK or CRITICAL but got {r4['level']}"
print("[PASS] Escalating congestion + turbulent movement correctly triggers HIGH RISK.")

# Scenario 5: Sudden chaotic stampede / panic movement
print("\n--- SCENARIO 5: Sudden Chaotic Stampede / Panic Rush ---")
m5 = {'speed': 13.5, 'turbulence': 8.8, 'acceleration': 4.5, 'score': 96.0, 'is_panic': True, 'level': 'PANIC'}
b5 = behv_an.analyze(d4, m5)
for _ in range(10):
    r5 = risk_pr.predict(d4, m5, b5, people_count=20)
print(f"Count: {r5['person_count']}, Speed: {m5['speed']} px/f, Risk: {r5['score']}%, Level: {r5['level']}")
assert r5['level'] in ('HIGH RISK', 'CRITICAL'), f"Expected HIGH RISK or CRITICAL but got {r5['level']}"
print("[PASS] Chaotic stampede movement escalates to HIGH RISK/CRITICAL.")

# Scenario 6: Genuine threat / weapon detected
print("\n--- SCENARIO 6: Genuine Weapon Threat Detected ---")
w6 = {'detected': True, 'score': 95.0, 'weapons': [{'label': 'firearm', 'confidence': 95.0}]}
for _ in range(8):
    r6 = risk_pr.predict(d1, m1, b1, weapon_result=w6, people_count=1)
print(f"Count: {r6['person_count']}, Threat: {r6['breakdown']['threat_score']}%, Risk: {r6['score']}%, Level: {r6['level']}")
assert r6['level'] == 'CRITICAL', f"Expected CRITICAL but got {r6['level']}"
print("[PASS] Weapon detection immediately triggers CRITICAL life-safety status.")

print("\n=================================================================")
print("ALL 6 DYNAMIC REAL-TIME MONITORING SCENARIOS PASSED PERFECTLY!")
print("=================================================================")
