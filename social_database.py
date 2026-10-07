"""Completed directed social-network project, using SQLAlchemy and local SQLite."""
import ast
import csv
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, CheckConstraint, event, select
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

def create_database(database_url='sqlite:///:memory:'):
    """Create a database without deleting or resetting any existing file."""
    if not database_url.startswith('sqlite:///'): raise ValueError('This project uses local SQLite only')
    Base = declarative_base()
    friendships = Table('friendships', Base.metadata,
        Column('person_id', Integer, ForeignKey('people.id'), primary_key=True),
        Column('friend_id', Integer, ForeignKey('people.id'), primary_key=True),
        CheckConstraint('person_id != friend_id'))
    club_members = Table('club_members', Base.metadata,
        Column('person_id', Integer, ForeignKey('people.id'), primary_key=True),
        Column('club_id', Integer, ForeignKey('clubs.id'), primary_key=True))
    class Person(Base):
        __tablename__ = 'people'
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
        age = Column(Integer, CheckConstraint('age >= 0 AND age <= 130'), nullable=False)
        gender = Column(String, nullable=False)
        location = Column(String, nullable=False)
        friends = relationship('Person',secondary=friendships,primaryjoin=id==friendships.c.person_id,secondaryjoin=id==friendships.c.friend_id)
        clubs = relationship('Club',secondary=club_members,back_populates='members')
    class Club(Base):
        __tablename__ = 'clubs'
        id = Column(Integer,primary_key=True)
        description = Column(String,nullable=False,unique=True)
        members = relationship('Person',secondary=club_members,back_populates='clubs')
    engine = create_engine(database_url)
    @event.listens_for(engine,'connect')
    def enable_foreign_keys(connection,_): connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.info['models'] = (Club,Person,friendships,club_members)
    return session,Club,Person,friendships,club_members

def _list(value):
    if not isinstance(value,str) or len(value)>4096:raise ValueError('Invalid bounded list field')
    try: result = ast.literal_eval(value)
    except (ValueError,SyntaxError,RecursionError) as e:raise ValueError('List field must be a Python list literal') from e
    if not isinstance(result,list) or len(result)>200:raise ValueError('Expected a list of at most 200 items')
    return result

def read_members(csv_path):
    path = Path(csv_path)
    if not path.is_file() or path.stat().st_size>5_000_000:raise ValueError('Expected local CSV under 5 MB')
    fields=['ID','Name','Surname','Age','Gender','Location','Clubs','Friendships']
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=fields:raise ValueError('Incorrect CSV columns or order')
        records=[];seen=set()
        for row in reader:
            if len(records)>=10000:raise ValueError('At most 10000 members supported')
            if None in row or any(v is None for v in row.values()):raise ValueError('Malformed CSV row')
            try:person_id=int(row['ID']);age=int(row['Age'])
            except ValueError as e:raise ValueError('ID and age must be integers') from e
            if person_id<1 or person_id in seen or not 0<=age<=130:raise ValueError('Invalid/duplicate ID or age')
            for name in ['Name','Surname','Gender','Location']:
                if not row[name].strip() or len(row[name])>200:raise ValueError('Missing or oversized text field')
            clubs=_list(row['Clubs']);friends=_list(row['Friendships'])
            if any(not isinstance(c,str) or not c.strip() or len(c)>200 for c in clubs):raise ValueError('Invalid club description')
            if any(type(friend) is not int or friend<1 or friend==person_id for friend in friends):raise ValueError('Invalid or self friendship')
            records.append({'id':person_id,'name':row['Name'].strip()+' '+row['Surname'].strip(),'age':age,
                'gender':row['Gender'].strip(),'location':row['Location'].strip(),
                'clubs':sorted({c.strip() for c in clubs}),'friends':sorted(set(friends))})
            seen.add(person_id)
    if any(friend not in seen for r in records for friend in r['friends']):raise ValueError('Friend ID missing from CSV')
    return records

def load_data_from_csv(session,Club,Person,friendships,club_members,csv_path='members.csv'):
    """Validate all input first, then atomically replace this project graph."""
    records=read_members(csv_path)
    if session.new or session.dirty or session.deleted:raise ValueError('Commit unrelated pending changes before importing')
    try:
        # Association tables must be removed before referenced entities.
        session.execute(friendships.delete());session.execute(club_members.delete())
        session.query(Person).delete(synchronize_session=False);session.query(Club).delete(synchronize_session=False)
        session.expire_all()
        clubs={c:Club(description=c) for r in records for c in r['clubs']}
        session.add_all(clubs.values());session.flush()
        people={r['id']:Person(id=r['id'],name=r['name'],age=r['age'],gender=r['gender'],location=r['location'],
                    clubs=[clubs[c] for c in r['clubs']]) for r in records}
        session.add_all(people.values());session.flush()
        for r in records:people[r['id']].friends=[people[i] for i in r['friends']]
        session.commit()
    except Exception:
        session.rollback()
        raise

def _models(session):return session.info['models']

def _person(session,person_name):
    Person=_models(session)[1]
    people=session.query(Person).filter_by(name=person_name).all()
    if len(people)>1:raise ValueError('Ambiguous name; use a unique full name in this project query')
    return people[0] if people else None

def get_club_members(session,club_description):
    Club,Person,_,club_members=_models(session)
    return session.query(Person).join(club_members).join(Club).filter(Club.description==club_description).order_by(Person.id).all()

def get_friends_of_person(session,person_name):
    person=_person(session,person_name)
    return sorted(person.friends,key=lambda p:p.id) if person else []

def get_persons_who_consider_them_friend(session,person_name):
    person=_person(session,person_name)
    if person is None:return []
    _,Person,friendships,_=_models(session)
    return session.query(Person).join(friendships,Person.id==friendships.c.person_id).filter(friendships.c.friend_id==person.id).order_by(Person.id).all()

def demo(csv_path):
    session,Club,Person,friendships,members=create_database()
    try:
        load_data_from_csv(session,Club,Person,friendships,members,csv_path)
        return {'people':session.query(Person).count(),'clubs':session.query(Club).count(),
                'friendships':len(session.execute(select(friendships)).all()),
                'club_memberships':len(session.execute(select(members)).all())}
    finally:session.close();session.get_bind().dispose()

if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--csv',default=str(Path(__file__).with_name('example_members.csv')))
    args=p.parse_args();print(json.dumps(demo(args.csv),indent=2))
