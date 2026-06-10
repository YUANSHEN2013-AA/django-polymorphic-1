#!/bin/bash
# 自动生成测试报告
pytest example/pexp/tests/test_models.py --cov=pexp.models --cov-report=html --cov-report=term-missing
