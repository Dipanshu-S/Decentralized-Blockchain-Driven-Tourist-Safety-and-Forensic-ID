"""
Database Initialization Script
Run this to set up databases for the first time
"""
from db_manager import DatabaseManager
from mongo_manager import MongoManager
from loguru import logger
import sys


def init_databases():
    """Initialize SQLite and MongoDB"""
    
    logger.info("="*60)
    logger.info("🗄️ Initializing Smart Tourist Safety Databases")
    logger.info("="*60)
    
    try:
        # Initialize SQLite
        logger.info("Initializing SQLite...")
        db = DatabaseManager()
        logger.success("✅ SQLite initialized")
        
        # Initialize MongoDB
        logger.info("Initializing MongoDB...")
        mongo = MongoManager()
        logger.success("✅ MongoDB initialized")
        
        # Test connections
        logger.info("Testing connections...")
        
        # Test SQLite
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tourists")
        tourist_count = cursor.fetchone()[0]
        logger.info(f"SQLite: {tourist_count} tourists in database")
        
        # Test MongoDB
        feature_count = mongo.tourist_features.count_documents({})
        session_count = mongo.tracking_sessions.count_documents({})
        logger.info(f"MongoDB: {feature_count} features, {session_count} sessions")
        
        logger.info("="*60)
        logger.success("✅ All databases initialized successfully!")
        logger.info("="*60)
        
        # Close connections
        db.close()
        mongo.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = init_databases()
    sys.exit(0 if success else 1)
