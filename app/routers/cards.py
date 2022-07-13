from fastapi import APIRouter, Depends, Response, status

from app.models.models import (CardCreate, CardDB, CardPartialUpdate,
                               CardTortoise, CollectionTortoise)
from app.utils.utils import pagination


async def get_card_or_404(id: int) -> CardTortoise:
    """Get object from db or raise DoesNotExist exception."""
    return await CardTortoise.get(id=id)

router = APIRouter(
    prefix='/cards',
    tags=['cards']
)


@router.get('/')
async def read_cards(pagination: tuple[int, int] = Depends(pagination)) \
                     -> list[CardDB]:
    """Get all cards in app."""
    skip, limit = pagination
    cards = await CardTortoise.all().offset(skip).limit(limit)

    for card in cards:
        await card.fetch_related('collections')
    return [CardDB.from_orm(card) for card in cards]


@router.get('/{id}')
async def read_card(card: CardTortoise = Depends(get_card_or_404)) -> CardDB:
    """Get card with particular id."""
    await card.fetch_related('collections')
    return CardDB.from_orm(card)


@router.post('/', status_code=status.HTTP_201_CREATED)
async def save_card(card: CardCreate) -> CardDB:
    """Create card."""
    card_tortoise = await CardTortoise.create(
        **card.dict(exclude={'collections', })
    )

    if card.collections:
        collections: filter[CollectionTortoise] = filter(
            None,
            [await CollectionTortoise.get_or_none(id=col.id)
             for col in card.collections]
        )

        await card_tortoise.collections.add(*collections)

    await card_tortoise.fetch_related('collections')
    return CardDB.from_orm(card_tortoise)


@router.put('/{id}')
async def update_card(
        card_update: CardPartialUpdate,
        card: CardTortoise = Depends(get_card_or_404)) -> CardDB:
    """Update existing card."""
    card.update_from_dict(card_update.dict(exclude={'collections', },
                                           exclude_unset=True))
    await card.save()

    if card_update.collections:
        await card.fetch_related('collections')
        card_old_collections = set(card.collections)
        card_new_collections = set(filter(  # type: ignore
            None,
            [
                await CollectionTortoise.get_or_none(id=col.id)
                for col in card_update.collections
            ]
        ))
        collections_to_add = card_new_collections - card_old_collections
        collections_to_remove = card_old_collections - card_new_collections
        if collections_to_add:
            await card.collections.add(*collections_to_add)
        if collections_to_remove:
            await card.collections.remove(*collections_to_remove)

    await card.fetch_related('collections')
    return CardDB.from_orm(card)


@router.delete('/{id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(card: CardTortoise = Depends(get_card_or_404)):
    """Delete card."""
    await card.fetch_related('collections')
    for collection in card.collections:
        await card.collections.remove(collection)
    await card.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)