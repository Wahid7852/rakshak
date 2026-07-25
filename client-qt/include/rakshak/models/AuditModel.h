#pragma once
#include <QtCore/QAbstractTableModel>
#include <QtWidgets/QMainWindow>
#include <QtCore/QVector>
#include <QtCore/QString>
#include <QtCore/QVariant>
#include <QtCore/QModelIndex>

struct AuditRow {
    QString timestamp;
    QString actor;
    QString action;
    QString resource;
    QString status;
    QString hash;
};

class AuditModel : public QAbstractTableModel {
    Q_OBJECT
public:
    explicit AuditModel(QObject* parent = nullptr);
    int rowCount(const QModelIndex& parent = QModelIndex()) const override;
    int columnCount(const QModelIndex& parent = QModelIndex()) const override;
    QVariant data(const QModelIndex& index, int role = Qt::DisplayRole) const override;
    QVariant headerData(int section, Qt::Orientation orientation, int role = Qt::DisplayRole) const override;

    void addEvent(const QString& source, const QVariantMap& event);
private:
    QVector<AuditRow> m_rows;
};