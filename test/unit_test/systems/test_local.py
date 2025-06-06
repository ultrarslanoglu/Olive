# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------
from functools import partial
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

from olive.constants import Framework
from olive.evaluator.metric import AccuracySubType, LatencySubType, Metric, MetricType
from olive.evaluator.metric_result import MetricResult, joint_metric_key
from olive.evaluator.olive_evaluator import OliveEvaluatorConfig
from olive.hardware import DEFAULT_CPU_ACCELERATOR
from olive.model import PyTorchModelHandler
from olive.systems.local import LocalSystem
from test.unit_test.utils import get_accuracy_metric, get_custom_metric, get_latency_metric

# pylint: disable=attribute-defined-outside-init


class TestLocalSystem:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.system = LocalSystem()

    def test_run_pass(self):
        # setup
        p = MagicMock()
        p.run.return_value = PyTorchModelHandler("model_path")
        olive_model = MagicMock()
        output_model_path = "output_model_path"

        # execute
        self.system.run_pass(p, olive_model, output_model_path)

        # assert
        p.run.assert_called_once_with(olive_model.create_model(), output_model_path)

    METRIC_TEST_CASE: ClassVar[list[Metric]] = [
        (partial(get_accuracy_metric, AccuracySubType.ACCURACY_SCORE)),
        (partial(get_accuracy_metric, AccuracySubType.F1_SCORE)),
        (partial(get_accuracy_metric, AccuracySubType.PRECISION)),
        (partial(get_accuracy_metric, AccuracySubType.RECALL)),
        (partial(get_accuracy_metric, AccuracySubType.AUROC)),
        (partial(get_latency_metric, LatencySubType.AVG)),
        (partial(get_latency_metric, LatencySubType.MAX)),
        (partial(get_latency_metric, LatencySubType.MIN)),
        (partial(get_latency_metric, LatencySubType.P50)),
        (partial(get_latency_metric, LatencySubType.P75)),
        (partial(get_latency_metric, LatencySubType.P90)),
        (partial(get_latency_metric, LatencySubType.P95)),
        (partial(get_latency_metric, LatencySubType.P99)),
        (partial(get_latency_metric, LatencySubType.P999)),
        (get_custom_metric),
    ]

    @pytest.mark.parametrize(
        "metric_func",
        METRIC_TEST_CASE,
    )
    @patch("olive.evaluator.olive_evaluator.OliveEvaluator.get_user_config")
    @patch("olive.evaluator.olive_evaluator.OnnxEvaluator._evaluate_accuracy")
    @patch("olive.evaluator.olive_evaluator.OnnxEvaluator._evaluate_latency")
    @patch("olive.evaluator.olive_evaluator.OnnxEvaluator._evaluate_custom")
    def test_evaluate_model(
        self, mock_evaluate_custom, mock_evaluate_latency, mock_evaluate_accuracy, mock_get_user_config, metric_func
    ):
        # setup
        olive_model_config = MagicMock()
        olive_model = olive_model_config.create_model()
        olive_model.framework = Framework.ONNX

        metric = metric_func()
        evaluator_config = OliveEvaluatorConfig(metrics=[metric])
        # olive_model.framework = Framework.ONNX
        expected_res = MetricResult.parse_obj(
            {
                sub_metric.name: {
                    "value": 0.382715310,
                    "priority": sub_metric.priority,
                    "higher_is_better": sub_metric.higher_is_better,
                }
                for sub_metric in metric.sub_types
            }
        )
        mock_evaluate_custom.return_value = expected_res
        mock_evaluate_latency.return_value = expected_res
        mock_evaluate_accuracy.return_value = expected_res
        mock_get_user_config.return_value = (None, None, None)

        # execute
        actual_res = self.system.evaluate_model(olive_model_config, evaluator_config, DEFAULT_CPU_ACCELERATOR)
        # assert
        if metric.type == MetricType.ACCURACY:
            mock_evaluate_accuracy.assert_called_once_with(
                olive_model, metric, None, None, "cpu", "CPUExecutionProvider"
            )
        if metric.type == MetricType.LATENCY:
            mock_evaluate_latency.assert_called_once_with(
                olive_model, metric, None, None, "cpu", "CPUExecutionProvider"
            )
        if metric.type == MetricType.CUSTOM:
            mock_evaluate_custom.assert_called_once_with(
                olive_model, metric, None, None, None, "cpu", "CPUExecutionProvider"
            )

        joint_keys = [joint_metric_key(metric.name, sub_metric.name) for sub_metric in metric.sub_types]
        for joint_key in joint_keys:
            assert actual_res[joint_key].value == 0.38271531
