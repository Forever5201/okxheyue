"""
端到端测试：测试基于计划的AI编排器
"""

import unittest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# 将src目录添加到Python路径
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.plan_based_orchestrator import PlanBasedAIOrchestrator, PlanStep

class TestPlanBasedOrchestrator(unittest.TestCase):

    def setUp(self):
        """在每个测试前运行"""
        # 设置必要的环境变量
        os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
        self.orchestrator = PlanBasedAIOrchestrator(config_path="config/enhanced_config.yaml")

    @patch('src.plan_based_orchestrator.PlanBasedAIOrchestrator.send_ai_request')
    def test_full_analysis_flow_success(self, mock_send_ai_request):
        """测试完整的“计划-执行-报告”成功流程"""

        # --- Mock AI的响应 ---
        # 1. Mock生成计划的响应
        mock_plan_response = {
            'choices': [{
                'message': {
                    'content': '{"plan":[{"step":1,"description":"获取BTC-USDT-SWAP的1小时K线"},{"step":2,"description":"生成最终报告"}]}'
                }
            }]
        }
        # 2. Mock执行步骤1的响应 (调用get_kline_data工具)
        mock_step1_tool_call_response = {
            'choices': [{
                'message': {
                    'tool_calls': [{
                        'id': 'call_123',
                        'type': 'function',
                        'function': {
                            'name': 'get_kline_data',
                            'arguments': '{"instrument_id":"BTC-USDT-SWAP","granularity":"1H"}'
                        }
                    }]
                }
            }]
        }
        # 3. Mock执行步骤1工具调用后的响应 (返回结论)
        mock_step1_final_response = {
            'choices': [{
                'message': {'content': 'K线数据已获取并分析完毕，趋势向上。'}
            }]
        }
        # 4. Mock生成最终报告的响应
        mock_final_report_response = {
            'choices': [{
                'message': {'content': '这是最终的分析报告：市场趋势良好。'}
            }]
        }

        # 设置mock的调用顺序
        mock_send_ai_request.side_effect = [
            mock_plan_response,              # 生成计划
            mock_step1_tool_call_response,   # 步骤1 - 请求工具调用
            mock_step1_final_response,       # 步骤1 - 工具调用后，给出结论
            mock_final_report_response       # 生成报告
        ]

        # --- Mock工具的执行结果 ---
        with patch('src.plan_based_orchestrator.PlanBasedAIOrchestrator.execute_tool_call') as mock_execute_tool_call:
            # 设置工具调用的mock返回
            mock_tool_result = MagicMock()
            mock_tool_result.success = True
            mock_tool_result.data = {"kline": "...some data..."}
            mock_execute_tool_call.return_value = mock_tool_result

            # --- 执行分析 ---
            analysis_request = "分析BTC行情"
            result = self.orchestrator.analyze_market(analysis_request)

            # --- 断言结果 ---
            self.assertTrue(result['success'])
            self.assertIn('analysis_plan', result)
            self.assertIn('final_report', result)

            # 验证计划
            self.assertEqual(len(result['analysis_plan']), 2)
            self.assertEqual(result['analysis_plan'][0]['description'], "获取BTC-USDT-SWAP的1小时K线")
            self.assertEqual(result['analysis_plan'][0]['status'], "completed")

            # 验证最终报告
            self.assertEqual(result['final_report'], "这是最终的分析报告：市场趋势良好。")

            # 验证AI请求的调用次数
            self.assertEqual(mock_send_ai_request.call_count, 4)
            
            # 验证工具调用
            mock_execute_tool_call.assert_called_once()
            called_tool_args = mock_execute_tool_call.call_args[0][0]
            self.assertEqual(called_tool_args.name, 'get_kline_data')

if __name__ == '__main__':
    unittest.main()