#!/usr/bin/env python3
"""
测试可读订单ID API的示例脚本

使用方法:
1. 确保Django服务器正在运行: python manage.py runserver
2. 运行此脚本: python test_readable_order_api.py
"""

import requests
import json

# API配置
BASE_URL = "http://localhost:8000/api"


def test_get_order_by_readable_id(readable_order_id):
    """
    测试通过可读订单ID获取订单信息

    参数:
        readable_order_id (str): 10位可读订单ID
    """
    print("\n" + "="*60)
    print(f"测试: 通过可读ID查询订单")
    print(f"订单ID: {readable_order_id}")
    print("="*60)

    url = f"{BASE_URL}/orders/by-code/{readable_order_id}/"
    print(f"请求URL: {url}")

    try:
        response = requests.get(url)
        print(f"响应状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\n✅ 订单查询成功!")
            print(f"\n订单详情:")
            print(f"  - 订单ID (UUID): {data['order_id']}")
            print(f"  - 可读订单ID: {data['readable_order_id']}")
            print(f"  - 状态: {data['status']}")
            print(f"  - 消息: {data['message']}")

            print(f"\n患者信息:")
            print(f"  - 姓名: {data['patient']['name']}")
            print(f"  - MRN: {data['patient']['mrn']}")
            print(f"  - 出生日期: {data['patient']['dob']}")

            print(f"\n医生信息:")
            print(f"  - 姓名: {data['provider']['name']}")
            print(f"  - NPI: {data['provider']['npi']}")

            print(f"\n药物信息:")
            print(f"  - 药物名称: {data['medication']['name']}")
            print(f"  - 主要诊断: {data['medication']['primary_diagnosis']}")
            print(f"  - 其他诊断: {data['medication']['additional_diagnoses']}")
            print(f"  - 用药史: {data['medication']['medication_history']}")

            print(f"\n时间信息:")
            print(f"  - 创建时间: {data['created_at']}")
            print(f"  - 更新时间: {data['updated_at']}")

            if data['status'] == 'completed':
                print(f"\n📄 Care Plan信息:")
                print(f"  - 生成时间: {data['care_plan']['generated_at']}")
                print(f"  - LLM模型: {data['care_plan']['llm_model']}")
                print(f"  - 下载链接: {data['care_plan']['download_url']}")
                print(f"\nCare Plan内容预览:")
                print("-" * 60)
                content_preview = data['care_plan']['content'][:200]
                print(content_preview + "...")
                print("-" * 60)

        elif response.status_code == 404:
            error_data = response.json()
            print(f"\n❌ 订单未找到")
            print(f"错误消息: {error_data['message']}")
            print(f"查询的ID: {error_data['readable_order_id']}")

        else:
            print(f"\n❌ 请求失败")
            print(f"响应内容: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ 连接错误: 无法连接到服务器")
        print("请确保Django服务器正在运行: python manage.py runserver")

    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")


def test_case_insensitive():
    """测试大小写不敏感"""
    print("\n" + "="*60)
    print("测试: 大小写不敏感")
    print("="*60)

    # 假设有一个订单ID
    test_id = "A3K9L2M7P4"

    print(f"\n测试1: 全大写 - {test_id}")
    test_get_order_by_readable_id(test_id)

    print(f"\n测试2: 全小写 - {test_id.lower()}")
    test_get_order_by_readable_id(test_id.lower())

    print(f"\n测试3: 混合大小写 - a3K9l2M7p4")
    test_get_order_by_readable_id("a3K9l2M7p4")


def test_invalid_order_id():
    """测试无效的订单ID"""
    print("\n" + "="*60)
    print("测试: 无效订单ID")
    print("="*60)

    invalid_ids = [
        "INVALID123",
        "0000000000",
        "XXXXXXXXXX",
        "ABCDEF1234"  # 正确格式但不存在
    ]

    for invalid_id in invalid_ids:
        test_get_order_by_readable_id(invalid_id)


def print_usage_examples():
    """打印使用示例"""
    print("\n" + "="*60)
    print("API使用示例")
    print("="*60)

    print("\n1. 使用curl:")
    print("   curl -X GET http://localhost:8000/api/orders/by-code/A3K9L2M7P4/")

    print("\n2. 使用Python requests:")
    print("""
    import requests
    response = requests.get('http://localhost:8000/api/orders/by-code/A3K9L2M7P4/')
    data = response.json()
    print(data['status'])
    """)

    print("\n3. 使用JavaScript fetch:")
    print("""
    fetch('http://localhost:8000/api/orders/by-code/A3K9L2M7P4/')
      .then(response => response.json())
      .then(data => console.log(data.status));
    """)


def main():
    """主函数"""
    print("\n" + "="*60)
    print("可读订单ID API 测试脚本")
    print("="*60)

    # 打印使用示例
    print_usage_examples()

    # 提示用户输入订单ID进行测试
    print("\n" + "="*60)
    print("开始测试")
    print("="*60)

    print("\n请输入要测试的可读订单ID（或按Enter跳过）:")
    readable_order_id = input("> ").strip()

    if readable_order_id:
        test_get_order_by_readable_id(readable_order_id)
    else:
        print("\n跳过自定义测试")
        print("\n提示: 您需要先创建一个订单，然后使用返回的readable_order_id进行测试")
        print("创建订单的API: POST http://localhost:8000/api/orders/")

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
