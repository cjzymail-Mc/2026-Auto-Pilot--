"""把 Codex multi-agent namespace 展开为 function，并过滤 z.ai 不支持的工具。

codex 0.146 的协作工具位于 namespace(multi_agent_v1) 内；z.ai chat 接口只认
type=='function'，否则 400 tools[N].type illegal。请求钩子把已知协作 namespace
展开为带前缀的 function，响应钩子再恢复原名与 multi_agent_v1；同时删除
spawn_agent 的显式 model，让 child 继承当前 GLM 会话模型。其他 namespace /
web_search 等继续过滤。

注：.py 源码 Python3 默认按 UTF-8 读取，不受 Windows gbk locale 影响，中文注释安全。
"""
import json

from litellm.integrations.custom_logger import CustomLogger


class ToolTypeFilter(CustomLogger):
    MULTI_AGENT_NAMESPACE = "multi_agent_v1"
    CODEX_RESPONSE_NAMESPACE = MULTI_AGENT_NAMESPACE
    CHAT_FUNCTION_PREFIX = "collaboration__"

    def _filter(self, data):
        tools = data.get("tools")
        if isinstance(tools, list) and tools:
            kept = []
            for tool in tools:
                if not isinstance(tool, dict):
                    continue

                tool_type = tool.get("type")
                if tool_type == "function":
                    kept.append(tool)
                    continue

                if tool_type != "namespace":
                    continue

                namespace = tool.get("name")
                if namespace == self.MULTI_AGENT_NAMESPACE:
                    nested_tools = tool.get("tools")
                    if not isinstance(nested_tools, list):
                        raise ValueError(
                            f"Codex namespace {namespace!r} has no function tool list"
                        )
                    for nested in nested_tools:
                        if not isinstance(nested, dict) or nested.get("type") != "function":
                            raise ValueError(
                                f"Codex namespace {namespace!r} contains a non-function tool"
                            )
                        original_name = nested.get("name")
                        if not isinstance(original_name, str) or not original_name:
                            raise ValueError(
                                f"Codex namespace {namespace!r} contains an unnamed function tool"
                            )
                        flattened = dict(nested)
                        # Chat Completions 没有 namespace 字段。加前缀保留路由来源；
                        # 回包时再恢复原名并补 namespace=multi_agent_v1。
                        flattened["name"] = self.CHAT_FUNCTION_PREFIX + original_name
                        kept.append(flattened)
                    continue

                if isinstance(namespace, str) and namespace.startswith("multi_agent"):
                    raise ValueError(
                        f"Unsupported Codex multi-agent namespace {namespace!r}; "
                        f"expected {self.MULTI_AGENT_NAMESPACE!r}"
                    )

            names = []
            for tool in kept:
                name = tool.get("name")
                if not isinstance(name, str) or not name:
                    raise ValueError("Codex function tool is missing a non-empty name")
                if name in names:
                    raise ValueError(f"Duplicate Codex function tool name {name!r}")
                names.append(name)

            data["tools"] = kept
        return data

    @staticmethod
    def _get_field(value, name):
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    @staticmethod
    def _set_field(value, name, field_value):
        if isinstance(value, dict):
            value[name] = field_value
        else:
            setattr(value, name, field_value)

    @classmethod
    def _drop_spawn_agent_model(cls, value):
        """在完整 arguments 到达后删除不可用的 child model override。"""
        arguments = cls._get_field(value, "arguments")
        # 流式 response.output_item.added 会先给 arguments="" 的占位项；
        # 参数随后通过 delta 到达，最终 done item 才含完整 JSON。
        if arguments is None or arguments == "":
            return
        if not isinstance(arguments, str):
            raise ValueError("Codex spawn_agent function call has non-string arguments")
        try:
            payload = json.loads(arguments)
        except json.JSONDecodeError:
            # 参数 delta 可能暂时不是完整 JSON；保留原值，等待最终 item。
            return
        if not isinstance(payload, dict):
            raise ValueError("Codex spawn_agent function call arguments are not an object")
        if "model" in payload:
            del payload["model"]
            cls._set_field(
                value,
                "arguments",
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )

    @classmethod
    def _restore_codex_namespace(cls, value):
        """把 LiteLLM 生成的 function_call 恢复为 Codex namespace call。"""
        if value is None:
            return value
        if isinstance(value, (list, tuple)):
            for item in value:
                cls._restore_codex_namespace(item)
            return value

        value_type = cls._get_field(value, "type")
        value_name = cls._get_field(value, "name")
        if (
            value_type == "function_call"
            and isinstance(value_name, str)
            and value_name.startswith(cls.CHAT_FUNCTION_PREFIX)
        ):
            original_name = value_name[len(cls.CHAT_FUNCTION_PREFIX) :]
            if not original_name:
                raise ValueError("Empty Codex collaboration function name in response")
            if original_name == "spawn_agent":
                cls._drop_spawn_agent_model(value)
            cls._set_field(value, "name", original_name)
            cls._set_field(value, "namespace", cls.CODEX_RESPONSE_NAMESPACE)

        for child_field in ("item", "response", "output"):
            child = cls._get_field(value, child_field)
            if child is not None and child is not value:
                cls._restore_codex_namespace(child)
        return value

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        return self._filter(data)

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        return self._restore_codex_namespace(response)

    async def async_post_call_streaming_iterator_hook(
        self, user_api_key_dict, response, request_data
    ):
        async for item in response:
            yield self._restore_codex_namespace(item)


proxy_handler_instance = ToolTypeFilter()
