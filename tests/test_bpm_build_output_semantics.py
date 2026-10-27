"""D22（review|content|active_output_semantics，V3 §12.1）配套测试：
verify_bpm_build 真实输入输出语义 fill_only 化——missing/supplied/waived 三层，
specific_create_and_save_instruction 不再无条件列为 missing。"""
import unittest

import tools.verification.build as verify_bpm_build


class RealInputLayerTests(unittest.TestCase):
    def test_fill_only_default_does_not_list_save_instruction_as_missing(self):
        layers = verify_bpm_build.real_input_layers(materials_dir=None, save_instruction_required=False)
        self.assertNotIn("specific_create_and_save_instruction", layers["missing"])
        waived = [item["item"] for item in layers["waived"]]
        self.assertIn("specific_create_and_save_instruction", waived)
        reason = layers["waived"][0]["reason"]
        self.assertIn("fill_only", reason)
        self.assertIn("untested", reason)

    def test_default_still_reports_genuinely_missing_inputs(self):
        layers = verify_bpm_build.real_input_layers(materials_dir=None, save_instruction_required=False)
        # 模板身份缺口真实存在（PENDING_HUMAN_NONBLOCKING）；未供料时材料目录仍报缺。
        self.assertIn("exact_history_template_number", layers["missing"])
        self.assertIn("current_material_directory", layers["missing"])

    def test_supplied_materials_dir_moves_directory_out_of_missing(self):
        layers = verify_bpm_build.real_input_layers(
            materials_dir="feature01-细化报销skill/12月公出-发票", save_instruction_required=False)
        self.assertNotIn("current_material_directory", layers["missing"])
        supplied = {item["item"]: item for item in layers["supplied"]}
        self.assertEqual(supplied["current_material_directory"]["status"], "supplied")
        self.assertIn("exact_history_template_number", layers["missing"])

    def test_explicit_save_requirement_restores_missing_semantics(self):
        layers = verify_bpm_build.real_input_layers(
            materials_dir="some/dir", save_instruction_required=True)
        self.assertIn("specific_create_and_save_instruction", layers["missing"])
        self.assertEqual(layers["waived"], [])

    def test_layer_union_is_stable_and_order_preserved(self):
        layers = verify_bpm_build.real_input_layers(None, False)
        self.assertEqual(layers["missing"], ["exact_history_template_number", "current_material_directory"])
        # 三层互斥：同一 item 不得同时出现在 missing 与 waived/supplied。
        waived_items = {item["item"] for item in layers["waived"]}
        self.assertFalse(set(layers["missing"]) & waived_items)


if __name__ == "__main__":
    unittest.main()
