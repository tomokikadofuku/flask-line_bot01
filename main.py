# -*- coding: utf-8 -*-

#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import os
import sys
import re
import slackweb
from argparse import ArgumentParser
from flask import Flask, request, abort, jsonify
from flask_sqlalchemy import SQLAlchemy

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)

channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
channel_slack_token = os.getenv('SLACK_PYTHON', None)
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

## ### 一旦データベースを作り直す
##   from main import db
##   db.drop_all()
##   db.create_all()

# モデル
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.String(200), unique=True)

    def __init__(self, source_id):
        self.source_id = source_id

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    bought = db.Column(db.Boolean, default=False)

    def __init__(self, name, user_id, bought):
        self.name = name
        self.user_id = user_id
        self.bought = bought

    def __repr__(self):
        return '<Item %r>' % self.bought

## ### DB直接入力
##   url = ItemUrl('hoge','https://hoeghoge')
##   db.session.add(url)
##   db.session.commit()

class ItemUrl(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30))
    url = db.Column(db.String(200))

    def __init__(self, name, url):
        self.name = name
        self.url = url

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def message_text(event):
    # 買う！！などだと空白が生まれちゃう。＝＞これにも対応したい。
    if event.message.text == "買う！" or event.message.text == "買う!":
        r_text = "何を買うんですか？"

    elif event.message.text == "買った！" or event.message.text == "買った!":
        r_text = "何を買ったんですか？"

    elif event.message.text == "私のID":
        r_text = str(event.source.user_id)

    elif "ヘルプ" in event.message.text:
        r_text = "例\n\n『ネギ買う！』\nと入力すると、ネギを買うものメモにいれるよ♪\n\n『ネギ買った！』\nと入力するとネギをメモから外すよ♪"

    elif event.message.text in ["リスト", "りすと", "りすと！", "りすと!", "リスト！", "リスト!", "メモ", "めも"]:
        r_text = "現在のお買い物リストです。"
        source_id = str(event.source.user_id)
        user_id = User.query.filter_by(source_id=source_id).first().id
        items = Item.query.filter_by(user_id=user_id).filter(Item.bought == False).all()
        a = ""
        for item in items:
            a = a + item.name + '\n'

        r_text = r_text + '\n\n' + a

        slack = slackweb.Slack(url=channel_slack_token)
        slice_id = source_id[0:5]
        slack.notify(text=slice_id +"がリストを開いたよ")
    
    elif event.message.text == "全部買った！" or event.message.text == "全部買った!":
        source_id = str(event.source.user_id)

        if not User.query.filter_by(source_id=source_id).first():
            r_text = "ユーザーが作成されていません！まずは、「〇〇買う！」と買いたいものを入力してみよう！"
        else:
            user_id= User.query.filter_by(source_id=source_id).first().id
            items = Item.query.filter_by(user_id=user_id, bought=False).all()
            for item in items:
                item.bought = True
                db.session.add(item)
                db.session.commit()
            r_text = "全部買ったのでお買い物リストから取り除いたよ！"

    elif event.message.text == "買ったもの":
        r_text = "過去28日間のうちに購入したものです!"
        source_id = str(event.source.user_id)
        if not User.query.filter_by(source_id=source_id).first():
            r_text = "ユーザーが作成されていません！まずは、「〇〇買う！」と買いたいものを入力してみよう！"
        else:
            user_id = User.query.filter_by(source_id=source_id).first().id
            items = Item.query.filter_by(user_id=user_id).filter(Item.bought == True).all()
            a = ""
            count = 0
            for item in items:
                a = a + item.name + '\n'
                count = count + 1
            b = str(count) + "点、買ったよ！"

            r_text = r_text + '\n\n' + a + '\n\n' + b

    elif "買う！" in event.message.text or "買う!" in event.message.text:
        user_text = event.message.text
        source_id = str(event.source.user_id)
        data = re.split( r'買う', user_text )
        print(data)
        data_list = data[0].split('\n')
        item = data_list[0]

        if not User.query.filter_by(source_id=source_id).first():
            user = User(source_id=source_id)
            db.session.add(user)
            db.session.commit()
            slack = slackweb.Slack(url=channel_slack_token)
            slack.notify(text="新規アカウントが作成されたよ！" + source_id)

        user_id= User.query.filter_by(source_id=source_id).first().id
        item_o = Item(name=item, user_id=user_id, bought=False)
        db.session.add(item_o)
        db.session.commit()
        r_text = item + " をお買い物リストに入れたよ"

        slack = slackweb.Slack(url=channel_slack_token)
        slice_id = source_id[0:5]
        slack.notify(text=slice_id + "が" + item + "を追加したよ！")

    elif "買った！" in event.message.text or "買った!" in event.message.text:
        user_text = event.message.text
        source_id = str(event.source.user_id)
        data = re.split( r'買った', user_text )
        print(data)
        item = data[0]

        if not User.query.filter_by(source_id=source_id).first():
            user = User(source_id=source_id)
            db.session.add(user)
            db.session.commit()
            r_text = "ユーザー登録をしたよ！"

        if User.query.filter_by(source_id=source_id).first():
            user_id= User.query.filter_by(source_id=source_id).first().id
            item_b = Item.query.filter(Item.user_id == user_id ).filter(Item.bought == False).filter(Item.name == item).first()
            item_b.bought = True
            db.session.add(item_b)
            db.session.commit()
            r_text = item + " をお買い物リストから除いたよ"

            slack = slackweb.Slack(url=channel_slack_token)
            slice_id = source_id[0:5]
            slack.notify(text=slice_id + "が" + item + "を購入したよ！")

    elif event.message.text == "おすすめ" or event.message.text == "オススメ" or event.message.text == "おすすめ商品":
        url = ItemUrl.query.first().url
        r_text = "作者志田による最近のおすすめ！\nお水をおうちに置いておこう！\n" + url

    elif "おはよ" in event.message.text:
        r_text = "おはようございます！"

    else:
        source_id = str(event.source.user_id)
        user_text = event.message.text
        r_text = "あなたがおっしゃったことは「" + user_text + "」ですね。\n操作について知りたい時は、「ヘルプ」と入力してみてね！"

        slack = slackweb.Slack(url=channel_slack_token)
        slice_id = source_id[0:5]
        slack.notify(text=slice_id + "が" + user_text + "と言ったよ")
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(r_text)
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)