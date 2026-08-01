import unittest

from pydantic import ValidationError

from backend.models.schemas import ConfigInfo, ExportRequest, LevelConfig
from backend.services.config_generator import ConfigGenerator


class RecTargetOffsetModelTests(unittest.TestCase):
    model_types = (ExportRequest, LevelConfig, ConfigInfo)

    def test_default_rec_target_offset(self):
        for model_type in self.model_types:
            with self.subTest(model=model_type.__name__):
                first = model_type()
                second = model_type()

                self.assertEqual(first.rec_target_offset, [0, 0, 0, 0])
                self.assertIsNot(first.rec_target_offset, second.rec_target_offset)

    def test_accepts_four_integers_including_negative_values(self):
        for model_type in self.model_types:
            with self.subTest(model=model_type.__name__):
                model = model_type(rec_target_offset=[-10, 20, -30, 40])
                self.assertEqual(model.rec_target_offset, [-10, 20, -30, 40])

    def test_rejects_arrays_whose_length_is_not_four(self):
        for model_type in self.model_types:
            for value in ([], [1, 2, 3], [1, 2, 3, 4, 5]):
                with self.subTest(model=model_type.__name__, value=value):
                    with self.assertRaises(ValidationError):
                        model_type(rec_target_offset=value)

    def test_rejects_non_integer_items(self):
        for model_type in self.model_types:
            for value in (
                [1, 2, "3", 4],
                [1, 2, 3.0, 4],
                [1, 2, True, 4],
            ):
                with self.subTest(model=model_type.__name__, value=value):
                    with self.assertRaises(ValidationError):
                        model_type(rec_target_offset=value)


class RecTargetOffsetConfigGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.generator = ConfigGenerator()
        self.offset = [-10, 20, -30, 40]

    def test_ocr_navigation_nodes_generate_target_offset(self):
        cases = (
            ("活动", "抄作业找到关卡-活动"),
            ("活动有分级", "抄作业找到关卡-活动分级"),
            ("其他", "抄作业找到关卡-OCR"),
        )

        for level_type, node_name in cases:
            with self.subTest(level_type=level_type):
                config = {}
                level_config = LevelConfig(
                    level_type=level_type,
                    level_recognition_name="测试关卡",
                    difficulty="困难",
                    rec_target_offset=self.offset,
                )

                self.generator._add_navigation_nodes(config, level_config)

                self.assertEqual(config[node_name]["target_offset"], self.offset)
                if level_type == "活动有分级":
                    self.assertNotIn("target_offset", config["抄作业选择活动分级"])

    def test_reverse_restores_rec_target_offset(self):
        cases = (
            ("抄作业找到关卡-活动", "活动"),
            ("抄作业找到关卡-活动分级", "活动有分级"),
            ("抄作业找到关卡-OCR", "其他"),
        )

        for node_name, expected_level_type in cases:
            with self.subTest(node=node_name):
                config = {
                    "抄作业点左上角重开": {"next": ["重开确认", node_name]},
                    node_name: {
                        "expected": "测试关卡",
                        "target_offset": self.offset,
                    },
                }

                result = self.generator.reverse(config)

                self.assertEqual(result["config_info"]["level_type"], expected_level_type)
                self.assertEqual(result["config_info"]["rec_target_offset"], self.offset)

    def test_reverse_old_config_without_target_offset_uses_default(self):
        config = {
            "抄作业点左上角重开": {
                "next": ["重开确认", "抄作业找到关卡-活动"]
            },
            "抄作业找到关卡-活动": {"expected": "测试关卡"},
        }

        result = self.generator.reverse(config)

        self.assertEqual(result["config_info"]["rec_target_offset"], [0, 0, 0, 0])

    def test_reverse_invalid_target_offset_uses_default(self):
        invalid_values = ([1, 2, 3], [1, 2, "3", 4], [1, 2, True, 4])

        for invalid_value in invalid_values:
            with self.subTest(value=invalid_value):
                config = {
                    "抄作业点左上角重开": {
                        "next": ["重开确认", "抄作业找到关卡-OCR"]
                    },
                    "抄作业找到关卡-OCR": {
                        "expected": "测试关卡",
                        "target_offset": invalid_value,
                    },
                }

                result = self.generator.reverse(config)

                self.assertEqual(result["config_info"]["rec_target_offset"], [0, 0, 0, 0])

    def test_generate_then_reverse_preserves_rec_target_offset(self):
        level_config = LevelConfig(
            level_type="活动",
            level_recognition_name="测试关卡",
            rec_target_offset=self.offset,
        )

        generated = self.generator.generate({"1": [["1普"]]}, level_config)
        reversed_config = self.generator.reverse(generated)

        self.assertEqual(reversed_config["config_info"]["rec_target_offset"], self.offset)
        self.assertEqual(reversed_config["config_info"]["level_recognition_name"], "测试关卡")


if __name__ == "__main__":
    unittest.main()
