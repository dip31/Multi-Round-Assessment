"""
Shortlister — RabbitMQ consumer for the screening pipeline.

Listens on `profile_parsed_queue` for candidate processing events.
Delegates ALL business logic to processor.py.
After processing, publishes result to the next queue.
"""
import json
import logging
import asyncio
from config import RABBITMQ_URL
from shared.db.database import db_session
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from screening.processor import process_candidate

logger = logging.getLogger(__name__)

# Queue configuration
QUEUE_NAME = "profile_parsed_queue"
NEXT_QUEUE = "candidate_screened_queue"


async def process_candidate_event(payload: dict):
    """
    Process a profile.parsed event from candidate intake.
    This is called by the event bus when a new candidate is parsed and ready for screening.
    """
    try:
        candidate_id = payload.get("candidate_id")
        job_id = payload.get("job_id")
        
        if not candidate_id:
            logger.error("Message missing candidate_id: %s", payload)
            return

        logger.info("Processing profile.parsed event for candidate: %s, job_id: %s", candidate_id, job_id)

        # Process with a fresh DB session
        with db_session() as db:
            result = process_candidate(candidate_id, db)
            if result:
                # Get the actual job_id from the result or payload
                result_job_id = job_id or result.get("job_id")
                
                # Publish result to next stage
                event_topic = EventTopics.CANDIDATE_SHORTLISTED if result["status"] == "shortlisted" else EventTopics.CANDIDATE_REJECTED
                
                result_payload = {
                    "candidate_id": result["candidate_id"],
                    "job_id": result_job_id,
                    "application_id": result.get("application_id"),
                    "status": result["status"],
                    "score": result["score"],
                    "is_duplicate": result["is_duplicate"],
                }
                
                await event_bus.publish(
                    event_topic,
                    result_payload,
                    agent="screening_shortlister"
                )
                
                logger.info("Published screening result for candidate %s: %s (score: %d, job_id: %s)", 
                           candidate_id, result["status"], result["score"], result_job_id)
            else:
                logger.warning("Processing returned None for candidate %s", candidate_id)

    except Exception as exc:
        logger.exception("Unexpected error processing message: %s", exc)


async def start_event_listener():
    """
    Subscribe to profile.parsed events from the event bus.
    This works with both RabbitMQ and in-memory fallback.
    """
    logger.info("✅ Screening shortlister subscribing to profile events")
    
    # Subscribe to profile.parsed events from candidate intake
    event_bus.subscribe(EventTopics.PROFILE_PARSED, process_candidate_event)
    
    logger.info("✅ Screening shortlister is now listening for profile.parsed events")


def consume():
    """
    Legacy RabbitMQ consumer - kept for backward compatibility.
    Use start_event_listener() instead for event bus integration.
    """
    import pika
    import urllib.parse
    
    # Parse RabbitMQ URL to get host
    parsed = urllib.parse.urlparse(RABBITMQ_URL)
    host = parsed.hostname or "localhost"
    
    logger.info("Connecting to RabbitMQ at %s ...", host)
    
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host)
        )
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        channel.basic_qos(prefetch_count=1)
        
        def _on_message(ch, method, properties, body):
            """Callback for incoming messages — parses, processes, acks."""
            try:
                data = json.loads(body)
                logger.info("Received message: %s", data)
                
                candidate_id = data.get("candidate_id")
                if not candidate_id:
                    logger.error("Message missing candidate_id: %s", data)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return

                # Process with a fresh DB session
                with db_session() as db:
                    result = process_candidate(candidate_id, db)
                    if result:
                        # Publish result
                        event_payload = {
                            "candidate_id": result["candidate_id"],
                            "status": result["status"],
                            "score": result["score"],
                            "is_duplicate": result["is_duplicate"],
                        }
                        
                        # Publish to appropriate queue
                        next_queue = NEXT_QUEUE if result["status"] == "shortlisted" else "candidate_rejected_queue"
                        channel.queue_declare(queue=next_queue, durable=True)
                        channel.basic_publish(
                            exchange="",
                            routing_key=next_queue,
                            body=json.dumps(event_payload),
                            properties=pika.BasicProperties(delivery_mode=2),
                        )
                        logger.info("Published to %s: %s", next_queue, event_payload)
                    else:
                        logger.warning("Processing returned None for candidate %s", candidate_id)

                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as exc:
                logger.exception("Unexpected error processing message: %s", exc)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_message)

        logger.info("Screening consumer started. Waiting on queue '%s' ...", QUEUE_NAME)
        print(f"[*] Screening consumer listening on '{QUEUE_NAME}'. Press CTRL+C to exit.")

        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Consumer stopped by user.")
            channel.stop_consuming()
        finally:
            connection.close()
            logger.info("RabbitMQ connection closed.")
            
    except Exception as e:
        logger.error("Failed to connect to RabbitMQ: %s. Use event bus integration instead.", e)
        logger.info("Run with: python -m screening.shortlister --event-bus")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    
    if "--event-bus" in sys.argv:
        # Use event bus integration (works with both RabbitMQ and in-memory)
        asyncio.run(start_event_listener())
    else:
        # Legacy direct RabbitMQ consumer
        consume()
