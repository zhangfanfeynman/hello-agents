import os
import sys
from typing import Optional
from openai import OpenAI
from hello_agents import HelloAgentsLLM

print("=" * 60, flush=True)
print("🚀 开始测试 Ollama 连接...", flush=True)
print("=" * 60, flush=True)

try:
    llm_client = HelloAgentsLLM(
        provider="ollama",
        model="llama3", # 需与 `ollama run` 指定的模型一致
        base_url="http://localhost:11434/v1",
        api_key="ollama" # 本地服务同样不需要真实 Key
    )
    
    print("\n✅ LLM 客户端创建成功", flush=True)
    print(f"📋 Provider: {llm_client.provider}", flush=True)
    print(f"📋 Model: {llm_client.model}", flush=True)
    print(f"📋 Base URL: {llm_client.base_url}", flush=True)
    
    # 准备消息
    messages = [{"role": "user", "content": "你好，请用一句话介绍你自己。"}]
    
    print("\n🔄 正在调用 Ollama API...\n", flush=True)
    
    # 发起调用，think等方法都已从父类继承，无需重写
    response_stream = llm_client.think(messages)
    
    # 打印响应
    print("\n📝 Ollama Response:", flush=True)
    print("-" * 60, flush=True)
    
    response_text = ""
    for chunk in response_stream:
        # chunk 已经是文本片段，可以直接使用
        print(chunk, end="", flush=True)
        response_text += chunk
    
    print("\n" + "-" * 60, flush=True)
    print(f"\n✅ 完成！共接收 {len(response_text)} 个字符", flush=True)
    print("=" * 60, flush=True)
    
except Exception as e:
    print(f"\n❌ 错误: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)