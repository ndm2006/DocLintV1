"""Local experimental classifier. Synthetic training is NOT acceptance evidence."""
import re
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

REVISION = 'local-logreg-synthetic-0.1'
from .template import SPECIAL_ROLES
ROLES = {'body', 'chapter', 'heading', 'keep'} | SPECIAL_ROLES

def features(text, bold=False, size=13):
    t = text.strip()
    return [min(len(t), 500)/100, len(t.split())/20,
            bool(re.match(r'^chương\s+[\dIVX]+', t, re.I)),
            bool(re.match(r'^\d+\.\d+(?:\.\d+)?\s+\S', t)),
            t.isupper(), bold, size/13, t.endswith(('.', ';', ':')), bool(re.match(r'^\d+[.)]\s', t))]

# Versioned, deterministic bootstrap examples; replace with a held-out evaluated dataset.
x, y = [], []
for n in range(1, 31):
    for text, role, bold, size in [
        (f'CHƯƠNG {n}. TỔNG QUAN HỆ THỐNG', 'chapter', True, 16),
        (f'Chương {n} Cơ sở lý thuyết', 'chapter', False, 13),
        (f'{n}.1 Phân tích yêu cầu', 'heading', True, 14),
        (f'{n}.2.1 Thiết kế hệ thống', 'heading', False, 13),
        ('Tài liệu trình bày phương pháp nghiên cứu và kết quả thực nghiệm của hệ thống. '*n, 'body', False, 13),
        ('Trong nghiên cứu này, chúng tôi sử dụng dữ liệu để đánh giá hiệu quả.', 'body', False, 11),
        (f'{n}. Phần tử trong danh sách.', 'keep', False, 13),
        ('TRƯỜNG ĐẠI HỌC BÁCH KHOA HÀ NỘI', 'keep', True, 16),
        ('Hình 1. Sơ đồ hệ thống', 'keep', False, 12),
        ('TÀI LIỆU THAM KHẢO', 'keep', True, 14),
    ]:
        x.append(features(text, bold, size)); y.append(role)
model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=0)).fit(np.array(x), y)

def predict(text, bold=False, size=13):
    probabilities = model.predict_proba([features(text, bold, size)])[0]
    i = int(np.argmax(probabilities))
    return str(model.classes_[i]), round(float(probabilities[i]), 3)
