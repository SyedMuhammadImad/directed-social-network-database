import csv
from pathlib import Path
import pytest
from sqlalchemy import event,select
from sqlalchemy.exc import IntegrityError
from social_database import *

FIELDS=['ID','Name','Surname','Age','Gender','Location','Clubs','Friendships']
ROWS=[[1,'Alex','Example',20,'unspecified','Fictional City',"['Hiking Club', 'Chess Club']",'[2]'],
      [2,'Blair','Example',21,'unspecified','Fictional City',"['Chess Club']",'[3]'],
      [3,'Casey','Example',22,'unspecified','Fictional City','[]','[1]']]

def write(path,rows=ROWS):
    with path.open('w',encoding='utf-8',newline='') as f:w=csv.writer(f);w.writerow(FIELDS);w.writerows(rows)
    return path

@pytest.fixture
def db(tmp_path):
    s,c,p,f,m=create_database()
    file=write(tmp_path/'members.csv');load_data_from_csv(s,c,p,f,m,file)
    yield s,c,p,f,m,file
    s.close();s.get_bind().dispose()

def test_directed_friendship_club_and_missing_queries(db):
    s,c,p,f,m,_=db
    assert [v.name for v in get_friends_of_person(s,'Alex Example')]==['Blair Example']
    assert [v.name for v in get_persons_who_consider_them_friend(s,'Alex Example')]==['Casey Example']
    assert [v.id for v in get_club_members(s,'Chess Club')]==[1,2]
    assert all(fn(s,'missing')==[] for fn in [get_friends_of_person,get_persons_who_consider_them_friend,get_club_members])

def test_import_honors_argument_repeated_replacement_and_empty_csv(db,tmp_path):
    s,c,p,f,m,file=db
    for _ in range(3):load_data_from_csv(s,c,p,f,m,file)
    assert s.query(p).count()==3 and s.query(c).count()==2
    assert len(s.execute(select(f)).all())==3 and len(s.execute(select(m)).all())==3
    empty=write(tmp_path/'empty.csv',[]);load_data_from_csv(s,c,p,f,m,empty)
    assert s.query(p).count()==s.query(c).count()==0

@pytest.mark.parametrize('column,value',[(0,1),(3,-1),(7,'[99]'),(7,'[True]'),(7,'[2, 1]'),(6,"__import__('os').system('echo bad')"),(6,"['']"),(1,'')])
def test_invalid_input_preserves_existing_graph(db,tmp_path,column,value):
    s,c,p,f,m,_=db;rows=[row.copy() for row in ROWS];rows[1][column]=value
    path=write(tmp_path/'invalid.csv',rows)
    with pytest.raises(ValueError):load_data_from_csv(s,c,p,f,m,path)
    assert s.query(p).count()==3 and len(s.execute(select(f)).all())==3

def test_database_failure_rolls_back_replacement(db,tmp_path):
    s,c,p,f,m,_=db
    def fail(connection,cursor,statement,parameters,context,executemany):
        if statement.startswith('INSERT INTO people'):raise RuntimeError('injected failure')
    event.listen(s.get_bind(),'before_cursor_execute',fail)
    try:
        with pytest.raises(RuntimeError):load_data_from_csv(s,c,p,f,m,write(tmp_path/'retry.csv'))
    finally:event.remove(s.get_bind(),'before_cursor_execute',fail)
    assert s.query(p).count()==3 and len(s.execute(select(f)).all())==3

def test_foreign_keys_constraints_and_ambiguous_name(db):
    s,c,p,f,m,_=db
    with pytest.raises(IntegrityError):s.execute(f.insert().values(person_id=1,friend_id=99));s.commit()
    s.rollback()
    s.add(p(id=4,name='Alex Example',age=20,gender='unspecified',location='Fictional City'));s.commit()
    with pytest.raises(ValueError):get_friends_of_person(s,'Alex Example')

def test_existing_file_is_not_deleted(tmp_path):
    url='sqlite:///'+str(tmp_path/'network.db')
    s,c,p,f,m=create_database(url);load_data_from_csv(s,c,p,f,m,write(tmp_path/'members.csv'))
    s.close();s.get_bind().dispose()
    s,c,p,f,m=create_database(url)
    assert s.query(p).count()==3
    s.close();s.get_bind().dispose()
