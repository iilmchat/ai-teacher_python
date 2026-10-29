# Design.md — AI Teacher for Python (Ассистент учителя для школьников по Python)

**Версия:** v0.1.0  
**Стек:** Python 3.12 + FastAPI | React 19 | PostgreSQL 17 + pgvector | Redis | Stockfish 17 | LM Studio / DeepSeek | Docker Compose  
**© 2026 RuChating (iilmchat)**

---

## 1. Обзор проекта

### 1.1 Цель
Создать интерактивного AI-ассистента для обучения школьников программированию на Python с тремя уровнями помощи:
- **Базовый** — подсказки и наводящие вопросы
- **Средний** — частичные объяснения с примерами
- **Продвинутый** — полные решения с разбором

### 1.2 Целевая аудитория
- Школьники 10-17 лет
- Учителя информатики
- Родители

### 1.3 Ключевые функции
1. Чат-бот с адаптивным уровнем помощи
2. Генерация и проверка заданий
3. Анализ кода с объяснением ошибок
4. Прогресс-обучение (от простого к сложному)
5. Административная панель для учителей

---

## 2. Архитектура системы

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Web App     │  │  Mobile App  │  │  Admin Panel │          │
│  │  (React 19)  │  │   (PWA)      │  │  (React 19)  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API GATEWAY                               │
│                   (FastAPI + Redis Cache)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Chat Service │  │ Task Service │  │ Code Service │          │
│  │              │  │              │  │              │          │
│  │ - LLM Chat   │  │ - Generator  │  │ - Analyzer   │          │
│  │ - Levels     │  │ - Validator  │  │ - Executor   │          │
│  │ - Context    │  │ - Progress   │  │ - Linter     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ User Service │  │ Admin Svc    │  │ Analytics    │          │
│  │              │  │              │  │  Service     │          │
│  │ - Auth       │  │ - Content    │  │              │          │
│  │ - Profile    │  │ - Monitoring │  │ - Metrics    │          │
│  │ - Progress   │  │ - LLMOps     │  │ - Reports    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ PostgreSQL   │  │    Redis     │  │  Vector DB   │          │
│  │    17        │  │   (Cache)    │  │ (pgvector)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ LM Studio /  │  │  Stockfish   │  │   LLM API    │          │
│  │  DeepSeek    │  │     17       │  │  (Optional)  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack Details

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | Python 3.12 + FastAPI | REST API, async processing |
| Frontend | React 19 + TypeScript | Modern SPA with hooks |
| Database | PostgreSQL 17 + pgvector | Primary storage + embeddings |
| Cache | Redis | Sessions, rate limiting, queues |
| LLM | LM Studio / DeepSeek | Code generation & analysis |
| Code Execution | Stockfish 17 | Sandboxed Python execution |
| Containerization | Docker Compose | Development & deployment |
| Real-time | WebSockets | Live chat streaming |

---

## 3. Структура проекта

```
ai-teacher_python/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── config.py                  # Settings & environment
│   │   ├── dependencies.py            # DI container
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── chat.py            # Chat endpoints
│   │   │   │   ├── tasks.py           # Task management
│   │   │   │   ├── code.py            # Code analysis
│   │   │   │   ├── auth.py            # Authentication
│   │   │   │   ├── users.py           # User management
│   │   │   │   └── admin.py           # Admin endpoints
│   │   │   └── websocket.py           # WebSocket handlers
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── llm/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py            # LLM interface
│   │   │   │   ├── deepseek.py        # DeepSeek client
│   │   │   │   ├── lm_studio.py       # LM Studio client
│   │   │   │   └── prompts/           # Prompt templates
│   │   │   ├── chat_service.py
│   │   │   ├── task_service.py
│   │   │   ├── code_service.py
│   │   │   ├── user_service.py
│   │   │   └── analytics_service.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── chat.py
│   │   │   ├── task.py
│   │   │   ├── code.py
│   │   │   └── analytics.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── chat.py
│   │   │   ├── task.py
│   │   │   └── code.py
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── security.py           # JWT, hashing
│   │   │   ├── executor.py           # Sandboxed execution
│   │   │   ├── linter.py             # Python linter
│   │   │   └── rate_limiter.py       # Rate limiting
│   │   │
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── database.py           # Async engine
│   │       ├── repositories/
│   │       └── migrations/
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_chat.py
│   │   ├── test_tasks.py
│   │   └── test_code.py
│   │
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chat/
│   │   │   ├── CodeEditor/
│   │   │   ├── Tasks/
│   │   │   ├── Progress/
│   │   │   └── Admin/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── store/
│   │   ├── types/
│   │   └── utils/
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── docs/
│   ├── README.md                     # Navigation hub
│   ├── SPEC.md                       # Full specification
│   ├── USER_GUIDE.md                 # User scenarios
│   ├── ASSISTANT_LEVELS.md           # Three levels explained
│   ├── MANUAL_TESTING_GUIDE.md       # QA checklist
│   ├── GETTING_STARTED.md            # Setup in 20 min
│   ├── ARCHITECTURE.md               # Architecture details
│   ├── DESIGN_ADMIN_AND_OPS.md       # Phase 7: admin, LLMOps
│   ├── LLM_EVAL.md                   # LLM-as-judge metrics
│   ├── RULES.md                      # Code standards
│   ├── PROMPT_CURRENT.md             # System prompts
│   ├── RELEASES.md                   # Release checklist
│   ├── CHANGELOG.md                  # Version history
│   └── KNOWN_ISSUES.md               # Known problems
│
├── docker/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── .env.example
│
├── scripts/
│   ├── setup.sh
│   └── deploy.sh
│
├── Design.md                         # THIS FILE
├── README.md
└── LICENSE
```

---

## 4. Модели данных

### 4.1 Core Entities

```python
# User Model
class User:
    id: UUID
    email: str
    username: str
    hashed_password: str
    role: Enum['student', 'teacher', 'admin']
    level: Enum['basic', 'intermediate', 'advanced']
    created_at: datetime
    last_active: datetime
    settings: JSON  # preferences, theme, etc.

# Chat Session
class ChatSession:
    id: UUID
    user_id: UUID
    level: Enum['basic', 'intermediate', 'advanced']
    created_at: datetime
    updated_at: datetime
    metadata: JSON

# Chat Message
class ChatMessage:
    id: UUID
    session_id: UUID
    role: Enum['user', 'assistant', 'system']
    content: str
    code_blocks: JSON  # extracted code
    created_at: datetime

# Task
class Task:
    id: UUID
    title: str
    description: str
    difficulty: Enum['easy', 'medium', 'hard']
    category: str  # loops, functions, etc.
    test_cases: JSON
    hints: JSON
    solution_template: str
    created_by: UUID  # teacher/admin

# User Task Progress
class UserTaskProgress:
    id: UUID
    user_id: UUID
    task_id: UUID
    status: Enum['not_started', 'in_progress', 'completed']
    attempts: int
    best_solution: str
    completed_at: datetime

# Code Execution
class CodeExecution:
    id: UUID
    user_id: UUID
    code: str
    output: str
    error: str
    execution_time: float
    created_at: datetime
```

### 4.2 Database Schema (PostgreSQL)

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student',
    level VARCHAR(20) NOT NULL DEFAULT 'basic',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settings JSONB DEFAULT '{}'
);

-- Chat sessions
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    level VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Chat messages with vector embeddings
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    code_blocks JSONB DEFAULT '[]',
    embedding vector(1536),  -- OpenAI embedding size
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    category VARCHAR(100),
    test_cases JSONB NOT NULL,
    hints JSONB DEFAULT '[]',
    solution_template TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- User progress
CREATE TABLE user_task_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'not_started',
    attempts INT DEFAULT 0,
    best_solution TEXT,
    completed_at TIMESTAMP,
    UNIQUE(user_id, task_id)
);

-- Code executions
CREATE TABLE code_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    output TEXT,
    error TEXT,
    execution_time FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_chat_messages_embedding ON chat_messages USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_chat_sessions_user ON chat_sessions(user_id);
```

---

## 5. API Design

### 5.1 RESTful Endpoints

#### Authentication
```
POST   /api/v1/auth/register       # Register new user
POST   /api/v1/auth/login          # Login
POST   /api/v1/auth/logout         # Logout
POST   /api/v1/auth/refresh        # Refresh token
GET    /api/v1/auth/me             # Current user info
```

#### Chat
```
POST   /api/v1/chat/sessions                # Create chat session
GET    /api/v1/chat/sessions                # List user sessions
GET    /api/v1/chat/sessions/{id}           # Get session with messages
DELETE /api/v1/chat/sessions/{id}           # Delete session
POST   /api/v1/chat/sessions/{id}/messages  # Send message
WebSocket /api/v1/chat/ws/{session_id}      # Real-time chat
```

#### Tasks
```
GET    /api/v1/tasks                        # List tasks (filterable)
GET    /api/v1/tasks/{id}                   # Get task details
POST   /api/v1/tasks/{id}/submit            # Submit solution
GET    /api/v1/tasks/progress               # User progress
```

#### Code
```
POST   /api/v1/code/execute                 # Execute code
POST   /api/v1/code/analyze                 # Analyze code
POST   /api/v1/code/lint                    # Lint code
```

#### Users
```
GET    /api/v1/users/me                     # Current user
PATCH  /api/v1/users/me                     # Update profile
GET    /api/v1/users/me/stats               # User statistics
```

#### Admin
```
GET    /api/v1/admin/users                  # List all users
PATCH  /api/v1/admin/users/{id}             # Update user
DELETE /api/v1/admin/users/{id}             # Delete user
POST   /api/v1/admin/tasks                  # Create task
PUT    /api/v1/admin/tasks/{id}             # Update task
DELETE /api/v1/admin/tasks/{id}             # Delete task
GET    /api/v1/admin/analytics              # System analytics
```

### 5.2 WebSocket Protocol

```typescript
// Client -> Server
interface ClientMessage {
  type: 'chat' | 'ping';
  content: string;
  level?: 'basic' | 'intermediate' | 'advanced';
}

// Server -> Client
interface ServerMessage {
  type: 'token' | 'done' | 'error' | 'pong';
  content?: string;
  metadata?: any;
}
```

---

## 6. Три уровня ассистента

### 6.1 Базовый (Basic)
**Цель:** Научить думать, не давая готовых решений

**Поведение:**
- Задаёт наводящие вопросы
- Даёт подсказки общего характера
- Указывает на тип ошибки, но не исправляет
- Использует метафоры и аналогии

**Пример диалога:**
```
Ученик: Почему мой код не работает?
code = input()
if code = "hello":
    print("Hi!")

Ассистент: Посмотри внимательно на строку с if. 
В Python есть два разных оператора: один для сравнения, 
другой для присваивания. Какой используется у тебя?
```

### 6.2 Средний (Intermediate)
**Цель:** Частичная помощь с объяснением концепций

**Поведение:**
- Объясняет ошибку с примерами
- Показывает правильный синтаксис
- Даёт аналогичный пример
- Сравнивает неправильный и правильный подход

**Пример диалога:**
```
Ученик: Почему мой код не работает?
[code тот же]

Ассистент: Проблема в операторе сравнения. 
В Python для сравнения используется ==, а = для присваивания.

Правильно:
if code == "hello":
    print("Hi!")

Сравнение: variable = value (присваивание)
           variable == value (сравнение)
```

### 6.3 Продвинутый (Advanced)
**Цель:** Полное решение с детальным разбором

**Поведение:**
- Показывает полное решение
- Детально объясняет каждую часть
- Предлагает альтернативные подходы
- Документирует код комментариями

**Пример диалога:**
```
Ученик: Почему мой код не работает?
[code тот же]

Ассистент: В коде ошибка в операторе сравнения. 
Вот исправленное решение с комментариями:

# Получаем ввод от пользователя
code = input()

# Используем == для сравнения (не = для присваивания)
if code == "hello":  # Сравниваем значение
    print("Hi!")

Объяснение:
1. = — оператор присваивания (x = 5)
2. == — оператор сравнения (if x == 5)

Альтернативный вариант:
match code:
    case "hello":
        print("Hi!")
```

---

## 7. LLM Integration

### 7.1 Prompt Engineering

```python
# Prompt templates for each level
SYSTEM_PROMPTS = {
    "basic": """Ты — терпеливый учитель Python для школьников.
    Твоя задача — помочь ученику самому найти решение.
    НЕ давай готовый код. Задавай наводящие вопросы.
    Используй простые аналогии из жизни.
    Поощряй попытки ученика.""",

    "intermediate": """Ты — учитель Python для школьников.
    Объясняй ошибки с примерами, но не показывай полное решение.
    Давай похожие примеры для понимания.
    Показывай правильный синтаксис без полного решения задачи.""",

    "advanced": """Ты — опытный преподаватель Python.
    Давай полные решения с детальными объяснениями.
    Комментируй каждую важную часть кода.
    Предлагай альтернативные подходы.
    Учти best practices и Pythonic стиль."""
}

# Context injection
def build_prompt(level: str, context: dict) -> str:
    base = SYSTEM_PROMPTS[level]
    # Add user context, previous messages, etc.
    return f"{base}\n\nContext: {context}"
```

### 7.2 LLM API Integration

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator

class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        pass
    
    @abstractmethod
    async def stream(
        self, 
        prompt: str,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        pass

class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
    
    async def generate(self, prompt: str, **kwargs) -> str:
        response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response.choices[0].message.content
    
    async def stream(self, prompt: str, **kwargs):
        stream = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            **kwargs
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

class LMStudioProvider(LLMProvider):
    # Similar implementation for local LM Studio
    pass
```

---

## 8. Code Execution Sandbox

### 8.1 Security Requirements
- Timeout: 5 секунд максимум
- No file system access
- No network access
- No dangerous imports (os, sys, subprocess)
- Memory limit: 128MB

### 8.2 Implementation

```python
import asyncio
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins

class SandboxedExecutor:
    def __init__(self, timeout: int = 5, memory_limit: int = 128):
        self.timeout = timeout
        self.memory_limit = memory_limit * 1024 * 1024
        self.allowed_modules = {
            'math', 'random', 'datetime', 'collections',
            'itertools', 'functools', 'string', 're'
        }
    
    async def execute(self, code: str) -> dict:
        try:
            # Compile with restrictions
            byte_code = compile_restricted(
                code, 
                '<sandbox>', 
                'exec'
            )
            
            # Safe builtins only
            safe_globals = {
                '__builtins__': safe_builtins,
                '__name__': '__main__'
            }
            
            # Capture output
            output_buffer = io.StringIO()
            
            with contextlib.redirect_stdout(output_buffer):
                # Execute with timeout
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        exec,
                        byte_code,
                        safe_globals
                    ),
                    timeout=self.timeout
                )
            
            return {
                'success': True,
                'output': output_buffer.getvalue()
            }
            
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': f'Execution timeout ({self.timeout}s)'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
```

---

## 9. Frontend Architecture

### 9.1 Component Structure

```
src/
├── components/
│   ├── Chat/
│   │   ├── ChatWindow.tsx         # Main chat container
│   │   ├── MessageList.tsx        # Message display
│   │   ├── MessageInput.tsx       # User input
│   │   ├── CodeBlock.tsx          # Code rendering
│   │   └── LevelSelector.tsx      # Level switcher
│   │
│   ├── CodeEditor/
│   │   ├── Editor.tsx             # Monaco editor wrapper
│   │   ├── OutputPanel.tsx        # Execution output
│   │   └── RunButton.tsx          # Execute button
│   │
│   ├── Tasks/
│   │   ├── TaskList.tsx           # Task catalog
│   │   ├── TaskCard.tsx           # Individual task
│   │   ├── TaskView.tsx           # Task detail view
│   │   └── ProgressBar.tsx        # Progress indicator
│   │
│   └── Layout/
│       ├── Header.tsx
│       ├── Sidebar.tsx
│       └── Footer.tsx
│
├── pages/
│   ├── Home.tsx
│   ├── Chat.tsx
│   ├── Tasks.tsx
│   ├── Profile.tsx
│   └── Admin/
│       ├── Dashboard.tsx
│       ├── Users.tsx
│       └── Tasks.tsx
│
├── hooks/
│   ├── useChat.ts
│   ├── useAuth.ts
│   └── useWebSocket.ts
│
└── store/
    ├── authSlice.ts
    ├── chatSlice.ts
    └── tasksSlice.ts
```

### 9.2 Key Features

#### Real-time Chat with Streaming
```typescript
// hooks/useChat.ts
export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  
  const ws = useWebSocket(`/api/v1/chat/ws/${sessionId}`);
  
  useEffect(() => {
    ws.onMessage((event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'token') {
        // Append token to last message
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last.role === 'assistant') {
            return [...prev.slice(0, -1), {
              ...last,
              content: last.content + data.content
            }];
          }
          return prev;
        });
      }
    });
  }, []);
  
  return { messages, sendMessage, isStreaming };
}
```

---

## 10. Deployment

### 10.1 Docker Compose

```yaml
# docker/docker-compose.yml
version: '3.9'

services:
  postgres:
    image: postgres:17
    environment:
      POSTGRES_DB: ai_teacher
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  backend:
    build:
      context: ../backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/ai_teacher
      REDIS_URL: redis://redis:6379
      LLM_PROVIDER: ${LLM_PROVIDER}
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}
    depends_on:
      - postgres
      - redis
    ports:
      - "8000:8000"
  
  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

### 10.2 Environment Variables

```bash
# .env.example
# Database
DB_USER=ai_teacher
DB_PASSWORD=secure_password_here
DATABASE_URL=postgresql://ai_teacher:secure_password_here@localhost:5432/ai_teacher

# Redis
REDIS_URL=redis://localhost:6379

# LLM
LLM_PROVIDER=deepseek  # or lm_studio
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# LM Studio (alternative)
LM_STUDIO_URL=http://localhost:1234/v1

# Security
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# App
APP_NAME="AI Teacher Python"
DEBUG=true
ALLOWED_ORIGINS=http://localhost:3000
```

---

## 11. 10 Этапов реализации

### Этап 1: Project Setup (День 1)
- [ ] Создать структуру директорий
- [ ] Настроить Poetry/requirements.txt
- [ ] Docker Compose конфигурация
- [ ] CI/CD базовая настройка

### Этап 2: Backend Core (День 2-3)
- [ ] FastAPI приложение
- [ ] PostgreSQL + SQLAlchemy async
- [ ] Redis connection
- [ ] Миграции (Alembic)

### Этап 3: Authentication (День 4)
- [ ] JWT authentication
- [ ] User registration/login
- [ ] Role-based access control
- [ ] Rate limiting

### Этап 4: Chat Service (День 5-6)
- [ ] LLM integration (DeepSeek/LM Studio)
- [ ] Chat session management
- [ ] WebSocket streaming
- [ ] Context management

### Этап 5: Three Levels (День 7)
- [ ] Prompt templates для 3 уровней
- [ ] Level switching logic
- [ ] Level-specific responses
- [ ] Testing each level

### Этап 6: Code Execution (День 8)
- [ ] Sandboxed executor
- [ ] Safe builtins configuration
- [ ] Timeout handling
- [ ] Output capture

### Этап 7: Task System (День 9)
- [ ] Task CRUD
- [ ] Task categories and difficulty
- [ ] Progress tracking
- [ ] Test case validation

### Этап 8: Frontend Base (День 10-11)
- [ ] React 19 setup с Vite
- [ ] Routing and layout
- [ ] Authentication flow
- [ ] API client setup

### Этап 9: Frontend Features (День 12-13)
- [ ] Chat interface с streaming
- [ ] Code editor (Monaco)
- [ ] Task management UI
- [ ] Progress visualization

### Этап 10: Admin & Polish (День 14-15)
- [ ] Admin panel
- [ ] Analytics dashboard
- [ ] Documentation
- [ ] Testing & deployment

---

## 12. Метрики успеха

### 12.1 Technical Metrics
- API response time < 200ms
- WebSocket latency < 50ms
- Code execution < 5s
- LLM streaming start < 2s
- Uptime > 99.5%

### 12.2 Product Metrics
- Daily Active Users (DAU)
- Average session duration
- Task completion rate
- User satisfaction (NPS)
- Error rate < 1%

### 12.3 Learning Metrics
- Progress through levels
- Code correctness improvement
- Hint usage frequency
- Task retry patterns

---

## 13. Безопасность

### 13.1 Authentication & Authorization
- JWT с коротким сроком жизни
- Refresh token rotation
- Password hashing (bcrypt)
- Rate limiting per user/IP

### 13.2 Code Execution Safety
- RestrictedPython для кода
- Timeout enforcement
- Memory limits
- No dangerous imports
- Sandboxed environment

### 13.3 Data Protection
- HTTPS only
- Encrypted passwords
- SQL injection prevention
- XSS protection
- CORS configuration

---

## 14. Мониторинг и логирование

### 14.1 Application Monitoring
- Structured logging (JSON)
- Error tracking (Sentry)
- Performance monitoring
- Health checks endpoints

### 14.2 LLM Monitoring
- Token usage tracking
- Response time metrics
- Error rate per model
- Cost tracking

### 14.3 Database Monitoring
- Query performance
- Connection pool stats
- Index usage
- Slow query log

---

## 15. Документация

### 15.1 Technical Documentation
- API documentation (OpenAPI/Swagger)
- Architecture diagrams
- Database schema
- Deployment guide

### 15.2 User Documentation
- Getting started guide
- User manual
- FAQ
- Video tutorials

### 15.3 Developer Documentation
- Contributing guidelines
- Code style guide
- Testing guide
- Release process

---

## 16. Следующие шаги

1. **Утвердить Design.md** — получить обратную связь
2. **Создать TODO** — детальный план задач
3. **Настроить проект** — структура и зависимости
4. **Начать реализацию** — по этапам

---

**Document Status:** Draft v0.1.0  
**Last Updated:** 2026-10-29  
**Author:** AI Teacher Team  
**Review Status:** Pending Approval
