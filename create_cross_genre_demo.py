#!/usr/bin/env python3
"""
Demo que muestra cómo funciona el cruce de géneros
"""
import asyncio
from music_recommendation_engine import MultiLayerMusicRecommender

async def show_genre_crossing():
    """Muestra cómo funciona el cruce inteligente de géneros"""
    recommender = MultiLayerMusicRecommender()

    print("🎼 DEMO: CRUCE INTELIGENTE DE GÉNEROS")
    print("=" * 50)
    print()

    # EJEMPLO PERFECTO: Eminem + Linkin Park deben conectar
    print("🔗 EJEMPLO DE CONEXIÓN INTELIGENTE:")
    print("   Si te gusta Eminem Y Linkin Park, el sistema encuentra:")
    print("   → Eminem están relacionados con Linkin Park")
    print("   → Pero el cruce inteligente los descubre como puente")
    print()

    # Escenario 1: Eminem + Linkin Park
    await recommender.recommend_multi_layer(["eminem", "linkin park"])
    print()

    # Escenario 2: Hip-hop puro (debería tener intersecciones reales)
    print("🤝 EJEMPLO DE INTERSECCIONES REALES:")
    await recommender.recommend_multi_layer(["eminem", "2pac"])

if __name__ == '__main__':
    asyncio.run(show_genre_crossing())
