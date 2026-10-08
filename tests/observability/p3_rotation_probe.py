"""Synthetic Docker json-file rotation source, no business access."""
import json
import time
time.sleep(10)  # Let service discovery attach before rotation.
for number in range(80):
    print(json.dumps({"namespace":"seckill","environment":"local","service":"order-worker","level":"INFO","event":"p3_rotation_validation","message":"rotation probe " + str(number) + " " + "x"*700}),flush=True)
    time.sleep(.02)
print(json.dumps({"namespace":"seckill","environment":"local","service":"order-worker","level":"INFO","event":"p3_rotation_validation","message":"p3-rotation-tail-confirmed"}),flush=True)
time.sleep(45)
