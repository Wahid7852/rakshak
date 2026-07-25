#pragma once
#include <QtCore/QSortFilterProxyModel>
#include <QtCore/QString>

class AlertsProxy : public QSortFilterProxyModel {
    Q_OBJECT
public:
    explicit AlertsProxy(QObject* parent = nullptr);
    void setSeverityFilter(const QString& sev);
    void setTextFilter(const QString& text);
protected:
    bool filterAcceptsRow(int source_row, const QModelIndex& source_parent) const;
private:
    QString m_severity = "All";
    QString m_text;
};