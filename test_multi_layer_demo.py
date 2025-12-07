#!/usr/bin/env python3
"""
Demo completa del sistema multi-capa con diferentes escenarios
"""
import asyncio
from music_recommendation_engine import MultiLayerMusicRecommender

async def demo_scenarios():
    """Muestra diferentes escenarios del sistema multi-capa"""
    recommender = MultiLayerMusicRecommender()

    print("🎼 DEMO COMPLETA: SISTEMA MULTI-CAPA DE RECOMENDACIONES")
    print("=" * 70)
    print()

    # ESCENARIO 1: Hip-hop puro (debería tener intersecciones)
    print("📀 ESCENARIO 1: HIP-HOP PURO")
    print("-" * 30)
    await recommender.recommend_multi_layer(["eminem", "2pac", "50 cent"])
    print()

    # ESCENARIO 2: Metal puro (debería tener intersecciones)
    print("🎸 ESCENARIO 2: METAL PURO")
    print("-" * 30)
    await recommender.recommend_multi_layer(["metallica", "iron maiden", "black sabbath"])
    print()

    # ESCENARIO 3: Mix hip-hop/metal (débil conexión)
    print("🎚️ ESCENARIO 3: HIP-HOP + METAL (MEZCLA)")
    print("-" * 30)
    await recommender.recommend_multi_layer(["eminem", "metallica"])

    print()
    print("✅ DEMO COMPLETADA: Sistema Multi-Capa Funcionando! 🎉")

if __name__ == '__main__':
    asyncio.run(demo_scenarios())
