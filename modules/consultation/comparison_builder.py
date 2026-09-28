"""고객용 비교표 제작기의 기존 메뉴 진입점."""

def run():
    from modules.consultation.enrollment_comparison import run as enrollment_run
    enrollment_run()
