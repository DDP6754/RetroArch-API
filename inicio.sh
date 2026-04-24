#!/bin/bash
uvicorn main:app --host 0.0.0.0 --port 4242 --proxy-headers --forwarded-allow-ips='*'