# Environment Variables (Configured on Render)
TOKEN = os.getenv(8842392958:AAFwQ8HPDscVef2Rrt232AiHcmJGSNOhPlo)
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
ai_client = OpenAI(api_key=OPENAI_API_KEY)
