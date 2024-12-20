import pytest
import numpy as np
from sqlalchemy import URL, create_engine, Column, Integer, select
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import OperationalError
from tidb_vector.sqlalchemy import VectorType, VectorAdaptor
import tidb_vector
from ..config import TestConfig


db_url = URL(
    "mysql+pymysql",
    username=TestConfig.TIDB_USER,
    password=TestConfig.TIDB_PASSWORD,
    host=TestConfig.TIDB_HOST,
    port=TestConfig.TIDB_PORT,
    database="test",
    query=(
        {"ssl_verify_cert": True, "ssl_verify_identity": True}
        if TestConfig.TIDB_SSL
        else {}
    ),
)

engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Item1Model(Base):
    __tablename__ = "sqlalchemy_item1"
    id = Column(Integer, primary_key=True)
    embedding = Column(VectorType())


class Item2Model(Base):
    __tablename__ = "sqlalchemy_item2"
    id = Column(Integer, primary_key=True)
    embedding = Column(VectorType(dim=3))


class TestSQLAlchemy:
    def setup_class(self):
        Item1Model.__table__.drop(bind=engine, checkfirst=True)
        Item1Model.__table__.create(bind=engine)

    def teardown_class(self):
        Item1Model.__table__.drop(bind=engine, checkfirst=True)

    def setup_method(self):
        with Session() as session:
            session.query(Item1Model).delete()
            session.commit()

    def test_insert_get_record(self):
        with Session() as session:
            item1 = Item1Model(embedding=[1, 2, 3])
            session.add(item1)
            session.commit()
            item1 = session.query(Item1Model).first()
            assert np.array_equal(item1.embedding, np.array([1, 2, 3]))
            assert item1.embedding.dtype == np.float32

    def test_insert_get_record_np(self):
        with Session() as session:
            item1 = Item1Model(embedding=np.array([1, 2, 3]))
            session.add(item1)
            session.commit()
            item1 = session.query(Item1Model).first()
            assert np.array_equal(item1.embedding, np.array([1, 2, 3]))
            assert item1.embedding.dtype == np.float32

    def test_empty_vector(self):
        with Session() as session:
            item1 = Item1Model(embedding=[])
            session.add(item1)
            session.commit()
            assert session.query(Item1Model).count() == 1
            item1 = session.query(Item1Model).first()
            assert np.array_equal(item1.embedding, np.array([]))
            assert item1.embedding.dtype == np.float32

    def test_get_with_different_dimensions(self):
        with Session() as session:
            item1 = Item1Model(embedding=[1, 2, 3])
            session.add(item1)
            session.commit()

            with pytest.raises(OperationalError) as excinfo:
                session.scalar(
                    select(Item1Model.embedding.l1_distance([1, 2, 3, 4]) < 0.1)
                )
            assert "vectors have different dimensions" in str(excinfo.value)

    def test_l1_distance(self):
        with Session() as session:
            item1 = Item1Model(embedding=[1, 2, 3])
            item2 = Item1Model(embedding=[1, 2, 3.2])
            session.add_all([item1, item2])
            session.commit()

            result = session.scalars(
                select(Item1Model).filter(
                    Item1Model.embedding.l1_distance([1, 2, 3.1]) < 0.2
                )
            ).all()
            assert len(result) == 2

            distance = Item1Model.embedding.l1_distance([1, 2, 3])
            items = (
                session.query(Item1Model.id, distance.label("distance"))
                .order_by(distance)
                .limit(5)
                .all()
            )
            assert len(items) == 2

    def test_l2_distance(self):
        with Session() as session:
            item1 = Item1Model(embedding=[1, 2, 3])
            item2 = Item1Model(embedding=[1, 2, 3.2])
            session.add_all([item1, item2])
            session.commit()

            result = session.scalars(
                select(Item1Model).filter(
                    Item1Model.embedding.l2_distance([1, 2, 3.1]) < 0.2
                )
            ).all()
            assert len(result) == 2

            distance = Item1Model.embedding.l2_distance([1, 2, 3])
            items = (
                session.query(Item1Model.id, distance.label("distance"))
                .order_by(distance)
                .limit(5)
                .all()
            )
            assert len(items) == 2
            assert items[0].distance == 0.0

    def test_cosine_distance(self):
        with Session() as session:
            item1 = Item1Model(embedding=[1, 2, 3])
            item2 = Item1Model(embedding=[1, 2, 3.2])
            session.add_all([item1, item2])
            session.commit()

            result = session.scalars(
                select(Item1Model).filter(
                    Item1Model.embedding.cosine_distance([1, 2, 3.1]) < 0.2
                )
            ).all()
            assert len(result) == 2

            distance = Item1Model.embedding.cosine_distance([1, 2, 3])
            items = (
                session.query(Item1Model.id, distance.label("distance"))
                .order_by(distance)
                .limit(5)
                .all()
            )
            assert len(items) == 2

    def test_negative_inner_product(self):
        with Session() as session:
            item1 = Item1Model(embedding=[1, 2, 3])
            item2 = Item1Model(embedding=[1, 2, 3.2])
            session.add_all([item1, item2])
            session.commit()

            result = session.scalars(
                select(Item1Model).filter(
                    Item1Model.embedding.negative_inner_product([1, 2, 3.1]) < -14.0
                )
            ).all()
            assert len(result) == 2

            distance = Item1Model.embedding.negative_inner_product([1, 2, 3])
            items = (
                session.query(Item1Model.id, distance.label("distance"))
                .order_by(distance)
                .limit(5)
                .all()
            )
            assert len(items) == 2
            assert items[1].distance == -14.0


class TestSQLAlchemyWithDifferentDimensions:
    def setup_class(self):
        Item2Model.__table__.drop(bind=engine, checkfirst=True)
        Item2Model.__table__.create(bind=engine)

    def teardown_class(self):
        Item2Model.__table__.drop(bind=engine, checkfirst=True)

    def setup_method(self):
        with Session() as session:
            session.query(Item2Model).delete()
            session.commit()

    def test_insert_get_record(self):
        with Session() as session:
            item = Item2Model(embedding=[1, 2, 3])
            session.add(item)
            session.commit()
            item = session.query(Item2Model).first()
            assert np.array_equal(item.embedding, np.array([1, 2, 3]))
            assert item.embedding.dtype == np.float32

    def test_get_with_different_dimensions(self):
        with Session() as session:
            item = Item2Model(embedding=[1, 2, 3])
            session.add(item)
            session.commit()

            with pytest.raises(OperationalError) as excinfo:
                session.scalar(
                    select(Item2Model.embedding.l1_distance([1, 2, 3, 4]) < 0.1)
                )
            assert "vectors have different dimensions" in str(excinfo.value)

    def test_l1_distance(self):
        with Session() as session:
            item1 = Item2Model(embedding=[1, 2, 3])
            item2 = Item2Model(embedding=[1, 2, 3.2])
            session.add_all([item1, item2])
            session.commit()

            result = session.scalars(
                select(Item2Model).filter(
                    Item2Model.embedding.l1_distance([1, 2, 3.1]) < 0.2
                )
            ).all()
            assert len(result) == 2

            distance = Item2Model.embedding.l1_distance([1, 2, 3])
            items = (
                session.query(Item2Model.id, distance.label("distance"))
                .order_by(distance)
                .limit(5)
                .all()
            )
            assert len(items) == 2

    def test_l2_distance(self):
        with Session() as session:
            item1 = Item2Model(embedding=[1, 2, 3])
            item2 = Item2Model(embedding=[1, 2, 3.2])
            session.add_all([item1, item2])
            session.commit()

            result = session.scalars(
                select(Item2Model).filter(
                    Item2Model.embedding.l2_distance([1, 2, 3.1]) < 0.2
                )
            ).all()
            assert len(result) == 2

            distance = Item2Model.embedding.l2_distance([1, 2, 3])
            items = (
                session.query(Item2Model.id, distance.label("distance"))
                .order_by(distance)
                .limit(5)
                .all()
            )
            assert len(items) == 2
            assert items[0].distance == 0.0

    def test_cosine_distance(self):
        with Session() as session:
            item1 = Item2Model(embedding=[1, 2, 3])
            item2 = Item2Model(embedding=[1, 2, 3.2])
            session.add_all([item1, item2])
            session.commit()

            result = session.scalars(
                select(Item2Model).filter(
                    Item2Model.embedding.cosine_distance([1, 2, 3.1]) < 0.2
                )
            ).all()
            assert len(result) == 2

            distance = Item2Model.embedding.cosine_distance([1, 2, 3])
            items = (
                session.query(Item2Model.id, distance.label("distance"))
                .order_by(distance)
                .limit(5)
                .all()
            )
            assert len(items) == 2
            assert items[0].distance == 0.0

    def test_negative_inner_product(self):
        with Session() as session:
            item1 = Item2Model(embedding=[1, 2, 3])
            item2 = Item2Model(embedding=[1, 2, 3.2])
            session.add_all([item1, item2])
            session.commit()

            result = session.scalars(
                select(Item2Model).filter(
                    Item2Model.embedding.negative_inner_product([1, 2, 3.1]) < -14.0
                )
            ).all()
            assert len(result) == 2

            distance = Item2Model.embedding.negative_inner_product([1, 2, 3])
            items = (
                session.query(Item2Model.id, distance.label("distance"))
                .order_by(distance)
                .limit(5)
                .all()
            )
            assert len(items) == 2
            assert items[1].distance == -14.0


class TestSQLAlchemyAdaptor:
    def setup_method(self):
        Item1Model.__table__.drop(bind=engine, checkfirst=True)
        Item1Model.__table__.create(bind=engine)
        Item2Model.__table__.drop(bind=engine, checkfirst=True)
        Item2Model.__table__.create(bind=engine)

    def teardown_method(self):
        Item1Model.__table__.drop(bind=engine, checkfirst=True)
        Item2Model.__table__.drop(bind=engine, checkfirst=True)

    def test_create_index_on_dyn_vector(self):
        adaptor = VectorAdaptor(engine)
        with pytest.raises(ValueError):
            adaptor.create_vector_index(
                Item1Model.embedding, distance_metric=tidb_vector.DistanceMetric.L2
            )
        assert adaptor.has_vector_index(Item1Model.embedding) is False

    def test_create_index_on_fixed_vector(self):
        adaptor = VectorAdaptor(engine)
        adaptor.create_vector_index(
            Item2Model.embedding, distance_metric=tidb_vector.DistanceMetric.L2
        )
        assert adaptor.has_vector_index(Item2Model.embedding) is True

        with pytest.raises(Exception):
            adaptor.create_vector_index(
                Item2Model.embedding, distance_metric=tidb_vector.DistanceMetric.L2
            )

        assert adaptor.has_vector_index(Item2Model.embedding) is True

        adaptor.create_vector_index(
            Item2Model.embedding,
            distance_metric=tidb_vector.DistanceMetric.L2,
            skip_existing=True,
        )

        adaptor.create_vector_index(
            Item2Model.embedding,
            distance_metric=tidb_vector.DistanceMetric.COSINE,
            skip_existing=True,
        )

    def test_index_and_search(self):
        adaptor = VectorAdaptor(engine)
        adaptor.create_vector_index(
            Item2Model.embedding, distance_metric=tidb_vector.DistanceMetric.L2
        )
        assert adaptor.has_vector_index(Item2Model.embedding) is True

        with Session() as session:
            session.add_all(
                [Item2Model(embedding=[1, 2, 3]), Item2Model(embedding=[1, 2, 3.2])]
            )
            session.commit()

            # l2 distance
            distance = Item2Model.embedding.cosine_distance([1, 2, 3])
            items = (
                session.query(Item2Model.id, distance.label("distance"))
                .order_by(distance)
                .limit(5)
                .all()
            )
            assert len(items) == 2
            assert items[0].distance == 0.0
