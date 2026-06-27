import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evaluation.evaluator import EvaluationRunner
from evaluation.report_writer import ReportWriter


async def main():
    runner = EvaluationRunner(case_file='evaluation/cases/ecommerce_spider_cases.yaml')
    report = await runner.evaluate_all()
    writer = ReportWriter()
    writer.write(report, prefix='ecommerce-spider')
    print('Done!')


if __name__ == "__main__":
    asyncio.run(main())
