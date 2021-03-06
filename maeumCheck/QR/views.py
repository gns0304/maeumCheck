from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.decorators import login_required
from .models import *
from .auth import *
from .user import *
from django.views.decorators.http import require_POST
import json
from django.http import JsonResponse
from django.contrib import auth
from django.core.paginator import Paginator

# Create your views here.

def login(request):
    return render(request, 'login.html')

def logout(request):
    auth.logout(request)
    return redirect('index')

def index(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    else:
        return render(request, 'index.html')

def error(request):
    return render(request, 'error.html')

@login_required
def registerPlace(request):
    return render(request, 'dashboard/register.html', {"type": 0})

@login_required
def registerMeeting(request):
    return render(request, 'dashboard/register.html', {"type": 1})

@login_required
def editPlace(request, placeId):
    place = get_object_or_404(Place, pk=placeId)
    return render(request, 'dashboard/edit.html', {"type": 0, "target": place})

@login_required
def editMeeting(request, meetingId):
    meeting = get_object_or_404(Meeting, pk=meetingId)
    if meeting.expired_at < datetime.datetime.today().date():
        return render(request, 'error.html', {"errorCode" : "종료된 모임은 수정할 수 없습니다."})
    else:
        return render(request, 'dashboard/edit.html', {"type": 1, "target": meeting})

@login_required
def createPlace(request):
    if(request.method == 'POST'):
        place = Place()
        address = request.POST.get('roadAddress') + ', ' + request.POST.get('detailAddress') + request.POST.get('extraAddress')
        place.name = request.POST.get('name')
        place.owner = request.user
        place.postcode = request.POST.get('postcode')
        place.address = address
        place.maxPeople = request.POST.get('quantity')
        place.nowPeople = 0
        place.congestion = 0
        place.recentQRToken = 0
        place.save()

        registerToken(0, place.id, settings.RETENTION_PERIOD)
    return redirect('index')

@login_required
def createMeeting(request):
    if(request.method == 'POST'):
        meeting = Meeting()
        address = request.POST.get('roadAddress') + ', ' + request.POST.get('detailAddress') + request.POST.get('extraAddress')
        meeting.name = request.POST.get('name')
        meeting.owner = request.user
        meeting.postcode = request.POST.get('postcode')
        meeting.address = address
        meeting.expired_at = request.POST.get('expiredDate')
        meeting.save()
        registerToken(1, meeting.id, settings.RETENTION_PERIOD)
    return redirect('index')

# Related to QR Auth

@login_required
def generateQR(request, type, token):
    return generateQRimage("{0}/auth/{1}/{2}/".format(settings.DEFAULT_DOMAIN, type, token))

def successQR(request):
    return render(request, 'auth/authSuccess.html')

@login_required
def authQR(request, type, token):
    type = int(type)

    if type == 0:
        records = PlaceRecord.objects.all().order_by('-id')
        for record in records:
            if get_object_or_404(PlaceQRToken, pk=record.Token_id).token == token:
                return render(request, 'error.html', {"errorCode": "이미 사용된 토큰입니다."})
    elif type == 1:
        records = MeetingRecord.objects.all().order_by('-id')
        for record in records:
            if get_object_or_404(MeetingQRToken, pk=record.Token_id).token == token:
                return render(request, 'error.html', {"errorCode": "이미 사용된 토큰입니다."})
    if type == 0:
        targetRecord = PlaceRecord()
        targetQRTokenId = get_object_or_404(PlaceQRToken, token=token).id
        targetRecord.Token = PlaceQRToken(pk=targetQRTokenId)
        name = get_object_or_404(PlaceQRToken, token=token).target.name
        id = get_object_or_404(PlaceQRToken, token=token).target.id
    elif type == 1:
        targetRecord = MeetingRecord()
        targetQRTokenId = get_object_or_404(MeetingQRToken, token=token).id
        targetRecord.Token = MeetingQRToken(pk=targetQRTokenId)
        name = get_object_or_404(MeetingQRToken, token=token).target.name
        id = get_object_or_404(MeetingQRToken, token=token).target.id

    targetRecord.visitor = request.user
    targetRecord.save()

    auth_at = targetRecord.visited_at

    registerToken(type, id, settings.RETENTION_PERIOD)
    return redirect('successQR')

@require_POST
@login_required
def refreshQR(request, type):
    type = int(type)

    token_requested = request.POST.get('token')
    targetId = request.POST.get('id')

    if type == 0:
        target = get_object_or_404(Place, pk=targetId)
    elif type == 1:
        target = get_object_or_404(Meeting, pk=targetId)

    token_now = target.recentQRToken

    if token_requested == token_now:
        response = {"isChanged": 0}
        return JsonResponse(response)
    else:
        response = {"isChanged": 1, 'codeQR': "{0}/auth/{1}/{2}/code".format(settings.DEFAULT_DOMAIN, type, token_now), 'token': token_now}
        return JsonResponse(response)


# Related to DashBoard

@login_required
def dashboard(request):
    username = refreshUsername(request)
    places = Place.objects.filter(owner=request.user).order_by('-id')[:1]
    meetings = Meeting.objects.filter(owner=request.user).order_by('-id')[:1]

    # 모임 정책에 대한 진행도 출력을 위한 사항
    today = datetime.datetime.today().date()

    if meetings[0].expired_at > today:
        isComplete = 0
    else:
        isComplete = 1


    return render(request, 'dashboard/dashboard.html', {'places': places, 'meetings': meetings, 'username': username, "isComplete":isComplete})


@login_required
def listPlace(request):
    targets = Place.objects.filter(owner=request.user).order_by('-id')
    paginator = Paginator(targets, 3)
    page = request.GET.get('page')
    # dashboard/place로만 접근했을 때 1번 pagination에 현재 표시를 위해
    if page == None:
        page = 1
    page_targets = paginator.get_page(page)
    return render(request, 'dashboard/list.html', {"targets": page_targets, 'type' :0, 'page': int(page)})

@login_required
def listMeeting(request):
    targets = Meeting.objects.filter(owner=request.user).order_by('-id')
    paginator = Paginator(targets, 3)
    page = request.GET.get('page')
    # dashboard/place로만 접근했을 때 1번 pagination에 현재 표시를 위해
    if page == None:
        page = 1
    page_targets = paginator.get_page(page)
    # 모임 정책에 대한 진행도 출력을 위한 사항
    today = datetime.datetime.today().date()

    return render(request, 'dashboard/list.html', {"targets": page_targets, 'type': 1, 'today':today, 'page': int(page)})

@login_required
def detailPlace(request, placeId):
    place = get_object_or_404(Place, pk=placeId)
    token = place.recentQRToken
    codeQR = settings.DEFAULT_DOMAIN + '/auth/0/' + token +'/code'
    if place.owner == request.user:
        return render(request, 'dashboard/detail.html', {'target': place, 'codeQR': codeQR, 'token': token, 'type': 0})
    else:
        return render(request, 'error.html', {"errorCode": "권한이 없습니다."})

@login_required
def detailMeeting(request, meetingId):
    meeting = get_object_or_404(Meeting, pk=meetingId)
    if meeting.expired_at < datetime.datetime.today().date():
        return render(request, 'error.html', {"errorCode" : "종료된 모임은 접근할 수 없습니다."})
    else:
        token = meeting.recentQRToken
        codeQR = settings.DEFAULT_DOMAIN + '/auth/1/' + token + '/code'
        if meeting.owner == request.user:
            return render(request, 'dashboard/detail.html', {'target': meeting, 'codeQR': codeQR, 'token': token, 'type': 1})
        else:
            return render(request, 'error.html', {"errorCode": "권한이 없습니다."})

@login_required
def deletePlace(request, placeId):
    place = get_object_or_404(Place, pk=placeId)

    if place.owner == request.user:
        placeTokens = PlaceQRToken.objects.filter(target=place.id)

        if len(placeTokens) != 0:
            errorCode = "{}에 대한 만료되지 않은 방문기록이 존재하여 삭제할 수 없습니다.".format(place.name)
            return render(request, 'error.html', {"errorCode": errorCode})
        else:
            place.delete()
            return redirect('listPlace')

@login_required
def deleteMeeting(request, meetingId):
    meeting = get_object_or_404(Meeting, pk=meetingId)

    if meeting.owner == request.user:
        meetingTokens = MeetingQRToken.objects.filter(target=meeting.id)

        if len(meetingTokens) != 0:
            errorCode = "{}에 대한 만료되지 않은 방문기록이 존재하여 삭제할 수 없습니다.".format(meeting.name)
            return render(request, 'error.html', {"errorCode": errorCode})
        else:
            meeting.delete()
            return redirect('listMeeting')

@login_required
def updatePlace(request, placeId):
    place = get_object_or_404(Place, pk=placeId)
    place.maxPeople = request.POST.get('quantity')
    place.nowPeople = request.POST.get('nowquantity')
    place.save()
    return redirect('listPlace')

def updateMeeting(request, meetingId):
    meeting = get_object_or_404(Meeting, pk=meetingId)
    meeting.expired_at = request.POST.get('expiredDate')
    meeting.save()
    return redirect('listMeeting')