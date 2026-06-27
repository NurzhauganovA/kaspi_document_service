# Отчёт - Document Processing Service

Тестовое задание. Сервис принимает документы из Kafka, операторы забирают их из очереди и принимают решение, результат уходит в выходной топик.

---

## Соответствие ТЗ

### Функциональные требования

| Требование | Статус                                                                                                                 |
|------------|------------------------------------------------------------------------------------------------------------------------|
| Получение документов из очереди и сохранение в БД | ✅ Kafka consumer, batch insert, идемпотентность по `external_id + source_topic`                                        |
| API для сотрудников с авторизацией и RBAC | ✅ JWT + роли operator / supervisor / admin                                                                             |
| Захват первого документа в очереди на себя | ✅ `POST /api/v1/documents/claim`, `SELECT FOR UPDATE SKIP LOCKED`                                                      |
| Принять или отклонить документ | ✅ `POST /api/v1/documents/{id}/decision`                                                                               |
| Статистика за период (отдельная роль) | ✅ `GET /api/v1/documents/statistics` - supervisor и admin                                                              |
| Документы в локальной БД с метками времени, оператором и решением | ✅ PostgreSQL: `created_at`, `updated_at`, `assigned_at`, `decision_at`, `assigned_to_id`, `status`, `rejection_reason` |
| Отправка в выходную очередь после решения | ✅ transactional outbox → Kafka `documents.processed`                                                                   |

### Нефункциональные требования

| Требование | Статус |
|------------|--------|
| Стабильная работа | ✅ healthchecks, retry при падении Kafka, graceful shutdown |
| Нет конкурентных ошибок при claim | ✅ `SKIP LOCKED` + интеграционный тест на параллельный claim |
| Среднее время ответа < 1 с | ✅ median 7 ms, p95 120 ms (см. `load_test_report.html`) |
| 100 одновременных пользователей | ✅ прогон 100 users / 120s, отчёт в репозитории |

### Что приложено к заданию

| Артефакт | Статус |
|----------|--------|
| Исходный код + Dockerfile | ✅ |
| docker-compose | ✅ PostgreSQL, Redis, Kafka (KRaft), API |
| Отчёт | ✅ этот файл |
| Скрипт нагрузочного теста | ✅ `scripts/locustfile.py` |
| HTML-отчёт нагрузки | ✅ `load_test_report.html` |

Стек по ТЗ: Python, FastAPI, SQLAlchemy, PostgreSQL, Docker, Kafka - всё используется. Redis добавлен для health-check и задела под кэш.

---

## Архитектура (кратко)

```
Kafka (incoming) → consumer → PostgreSQL (pending)
                                    ↓
              operator: claim → in_progress → decision
                                    ↓
                         outbox (та же транзакция)
                                    ↓
              outbox worker → Kafka (processed)
```

Слои: endpoints → controllers → services → repositories. Решение и запись в outbox - одна транзакция, чтобы не потерять сообщение при падении после commit.

---

## Как запустить

```bash
cp .env.example .env

docker compose up --build -d

docker compose exec api python scripts/seed_users.py
docker compose exec api python scripts/produce_documents.py --count 100
```

Проверка:

- Swagger: http://localhost:8000/docs  
- Health: http://localhost:8000/api/v1/health  
- Metrics: http://localhost:8000/metrics  

Тестовые пользователи после seed:

- admin / `Admin1234!`
- operator_1 … operator_50 / `Test1234!`
- supervisor_1 … supervisor_5 / `Test1234!`

Типичный сценарий:

1. `POST /api/v1/auth/login` — JSON `{"username","password"}`
2. `POST /api/v1/documents/claim` — Bearer token
3. `POST /api/v1/documents/{id}/decision` — `{"action": "accepted"}` или `"rejected"` + `rejection_reason`
4. Статистика (supervisor):  
   `GET /api/v1/documents/statistics?from_dt=2026-06-20&to_dt=2026-06-28`

Юнит-тесты (без Docker):

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/unit/ -q
```

E2E и integration - нужен PostgreSQL (`documents_test`).

---

## Нагрузочное тестирование

Перед запуском: стек поднят, пользователи засеяны, в Kafka достаточно документов (для 100 операторов — `produce_documents --count 5000+`).

```bash
./scripts/run_load_test.sh docker
# или: docker compose --profile loadtest run --rm locust
```

С хоста: `pip install locust` → `./scripts/run_load_test.sh`

Сценарии: 80% операторы (login → claim → decision), 20% супервайзеры (statistics + health).  
404 на пустую очередь в Locust — успех, не ошибка сервиса.

### Результаты (`load_test_report.html`)

100 users, spawn-rate 10, 120s:

| | Aggregated |
|--|--|
| Запросов | 5180 |
| Ошибок | 1 (0.02%) |
| Median | 7 ms |
| Average | 48 ms (steady state) |
| 95%ile | 120 ms |
| RPS | ~45–47 |

Claim median **7 ms**, health **5 ms**, statistics **11 ms**. Login медленнее на старте (bcrypt, cold start). Одна ошибка claim — разовый сетевой сбой (`status 0`), не логика API.

---

## Что бы я доработал для реального бизнес-сервиса

Это уже не scope тестового, но в проде я бы закладывал:

**Надёжность и данные**
- Отдельный worker-сервис для Kafka consumer/outbox - API не должен тянуть фоновые задачи в том же процессе, что HTTP.
- DLQ для сообщений, которые не удалось обработать после N попыток.
- Мониторинг outbox: алерт, если pending-события копятся дольше порога.
- Audit log: кто, когда и с каким решением - отдельно от бизнес-таблицы, для комплаенса.

**Безопасность**
- Refresh-токены или интеграция с корпоративным IdP (Keycloak/OAuth2), а не только HS256 JWT.
- Rate limit на claim/decision по оператору - защита от случайных циклов и злоупотреблений.
- Регистрация пользователей только через admin/API provisioning, не публичный signup - так и сделано, но нужен нормальный процесс онбординга.

**Операционка**
- CI/CD: lint, unit/e2e, миграции, образ в registry.
- Kubernetes + HPA по RPS/latency, а не один контейнер с 4 uvicorn workers.
- Grafana-дашборды и алерты (latency p95, error rate, Kafka lag, outbox backlog).
- Schema Registry / версионирование payload документов - сейчас JSONB без контракта.

**Продукт**
- Приоритеты и SLA в очереди (срочные документы первыми).
- Дефолтный период в statistics (например, последние 7 дней) - удобнее для UI.
- Пагинация и фильтры в статистике, экспорт в CSV для отчётности.
- Возможность вернуть документ в очередь (reassign / escalate) - типичный кейс в операционных центрах.

---

## Структура репозитория

```
app/
  api/v1/endpoints/     # HTTP
  controllers/          # оркестрация
  services/             # бизнес-логика
  repositories/         # SQLAlchemy
  workers/              # Kafka consumer, outbox relay
  domain/               # доменные исключения
scripts/
  locustfile.py         # нагрузка
  run_load_test.sh
  seed_users.py
  produce_documents.py
load_test_report.html   # результат Locust
tests/
  unit/ integration/ e2e/
alembic/                # миграции
docker-compose.yml
Dockerfile
```

---

Python 3.11, зависимости зафиксированы в `requirements.txt`.
