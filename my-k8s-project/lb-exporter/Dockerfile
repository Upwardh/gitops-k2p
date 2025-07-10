# Python 3.9 Slim 이미지 사용 (경량화)
FROM python:3.9-slim-buster

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일 복사
COPY lb-exporter.py .
COPY kcldx.py .
COPY kclinstance.py .
COPY kclutil.py .

# 포트 노출 (lb-exporter.py의 EXPORTER_PORT와 일치)
EXPOSE 9105

# 컨테이너 시작 시 실행될 명령어
CMD ["python", "lb-exporter.py"]
