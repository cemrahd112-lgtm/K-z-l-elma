package com.kizilelma.mobile

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.content.ContentValues

class LocalStore(context: Context) : SQLiteOpenHelper(context, "kizilelma.db", null, 1) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, body TEXT NOT NULL, created_at INTEGER NOT NULL)")
    }
    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
    fun add(role: String, body: String) {
        writableDatabase.insertOrThrow("messages", null, ContentValues().apply {
            put("role", role); put("body", body); put("created_at", System.currentTimeMillis())
        })
    }
    fun history(): List<Pair<String,String>> = readableDatabase.rawQuery(
        "SELECT role, body FROM messages ORDER BY id DESC LIMIT 100", null
    ).use { c -> buildList { while (c.moveToNext()) add(c.getString(0) to c.getString(1)) }.asReversed() }
}
