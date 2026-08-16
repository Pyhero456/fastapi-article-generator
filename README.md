# AI Article Generator API

A FastAPI backend that generates AI articles using CrewAI, with user authentication, subscription management, and payment tracking.

## Features

- User registration & login (JWT)
- Secure API with refresh tokens
- Article generation via CrewAI agents
- Subscription plans (Starter, Pro, Unlimited)
- Overage billing for extra articles
- Admin payment approval
- Rate limiting & logging

## Tech Stack

- FastAPI
- SQLAlchemy (SQLite)
- CrewAI
- JWT authentication
- Streamlit frontend (separate repo)

## Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate it: `source venv/bin/activate` (Mac/Linux) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Create a `.env` file inside the `crew/` folder with your API keys
6. Run the server: `uvicorn main:app --reload`

## Environment Variables (crew/.env)
NVIDIA_API_KEY=your_key
TAVILY_API_KEY=your_key
SECRET_KEY=your_secret


## Deployment

This API is deployed on Render. The frontend is on Streamlit Cloud.

## License

MIT
