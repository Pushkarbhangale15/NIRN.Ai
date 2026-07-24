# Architecture

```
                   USER

                     │

             React Frontend

                     │

                FastAPI Backend

                     │

      ┌──────────────┼───────────────┐

      │              │               │

   SQLite      Vector Database     LLM

                     │

                Embeddings

                     │

               Government GRs
```

## Workflow

1. Read Government Resolution
2. Chunk text
3. Generate embeddings
4. Store vectors
5. Retrieve similar chunks
6. Send retrieved context to LLM
7. Generate answer